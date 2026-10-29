"""Command-line entry point for tidyup."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .organizer import apply_moves, plan_sort


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
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _describe(move) -> str:
    return f"  {move.source.name} -> {move.destination.parent.name}/{move.destination.name}"


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = build_parser().parse_args(argv)

    try:
        moves = plan_sort(args.directory, recursive=args.recursive)
    except NotADirectoryError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 2

    if not moves:
        print("Nothing to tidy - the folder is already sorted.")
        return 0

    verb = "Would move" if args.dry_run else "Moved"
    print(f"{verb} {len(moves)} file(s) in {args.directory.resolve()}")
    for move in moves:
        print(_describe(move))

    if not args.dry_run:
        apply_moves(moves)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
