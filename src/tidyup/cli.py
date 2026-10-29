"""Command-line entry point for tidyup."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, journal
from .organizer import CATEGORY, DATE, Move, apply_moves, plan_sort


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser.

    Kept separate from :func:`main` so tests can inspect the parser without
    triggering the whole program.
    """
    parser = argparse.ArgumentParser(
        prog="tidyup",
        description=(
            "Sort a messy folder into tidy subfolders. "
            "Always preview with --dry-run first."
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


def _print_moves(verb: str, moves: Sequence[Move], root: Path) -> None:
    print(f"{verb} {len(moves)} file(s) in {root.resolve()}")
    for move in moves:
        print(f"  {move}")


def _run_undo(args: argparse.Namespace) -> int:
    try:
        moves = journal.plan_undo(args.directory)
    except FileNotFoundError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 1

    _print_moves("Would restore" if args.dry_run else "Restored", moves, args.directory)
    if not args.dry_run:
        journal.undo(args.directory)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = build_parser().parse_args(argv)

    if args.undo:
        return _run_undo(args)

    try:
        moves = plan_sort(args.directory, recursive=args.recursive, by=args.by)
    except NotADirectoryError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 2

    if not moves:
        print("Nothing to tidy - the folder is already sorted.")
        return 0

    _print_moves("Would move" if args.dry_run else "Moved", moves, args.directory)

    if not args.dry_run:
        journal.save(args.directory, moves)
        apply_moves(moves)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
