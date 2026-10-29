"""Command-line entry point for tidyup."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__, journal
from .organizer import CATEGORY, DATE, Move, TidyupError, apply_moves, plan_sort


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Kept separate from :func:`main` so tests can inspect the parser without
    triggering the whole program.
    """
    parser = argparse.ArgumentParser(
        prog="tidyup",
        description=(
            "Sort a messy folder into tidy subfolders. Always preview with --dry-run first."
        ),
    )
    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path("."),
        help="folder to tidy (default: current directory)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="show the plan without moving anything",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="also sort files inside subdirectories",
    )
    parser.add_argument(
        "-b",
        "--by",
        choices=(CATEGORY, DATE),
        default=CATEGORY,
        help="group by file type (default) or by modification date",
    )
    parser.add_argument(
        "-x",
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip files matching GLOB, relative to the folder (repeatable)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="print the plan or the restore as JSON",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="reverse the most recent run in the folder",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _payload(args: argparse.Namespace, moves: Sequence[Move]) -> dict[str, Any]:
    return {
        "root": str(args.directory.resolve()),
        "dry_run": bool(args.dry_run),
        "count": len(moves),
        "moves": [
            {"source": _relative(m.source, m.root), "destination": _relative(m.destination, m.root)}
            for m in moves
        ],
    }


def _report(args: argparse.Namespace, verb: str, moves: Sequence[Move]) -> None:
    if args.as_json:
        print(json.dumps(_payload(args, moves), indent=2))
        return
    print(f"{verb} {len(moves)} file(s) in {args.directory.resolve()}")
    for move in moves:
        print(f"  {move}")


def _run_undo(args: argparse.Namespace) -> int:
    try:
        moves = journal.plan_undo(args.directory)
    except FileNotFoundError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 1

    _report(args, "Would restore" if args.dry_run else "Restored", moves)
    if not args.dry_run:
        journal.undo(args.directory)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = build_parser().parse_args(argv)

    if args.undo:
        return _run_undo(args)

    try:
        moves = plan_sort(
            args.directory, recursive=args.recursive, by=args.by, exclude=args.exclude
        )
    except NotADirectoryError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 2
    except TidyupError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 2

    if not moves:
        if args.as_json:
            print(json.dumps(_payload(args, []), indent=2))
        else:
            print("Nothing to tidy - the folder is already sorted.")
        return 0

    _report(args, "Would move" if args.dry_run else "Moved", moves)

    if not args.dry_run:
        journal.save(args.directory, moves)
        apply_moves(moves)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
