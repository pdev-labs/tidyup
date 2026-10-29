"""Command-line entry point for tidyup."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__


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
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    build_parser().parse_args(argv)
    print("Nothing to do yet - pass a directory to tidy.", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
