"""Command-line entry point for tidyup."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import __version__, journal
from .duplicates import find_duplicates, total_wasted
from .organizer import (
    CATEGORY,
    DATE,
    EXTENSION,
    RENAME,
    SKIP,
    Move,
    TidyupError,
    apply_moves,
    plan,
    prune_empty_dirs,
)


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
        choices=(CATEGORY, DATE, EXTENSION),
        default=CATEGORY,
        help="group by category (default), modification date or extension",
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
        "--duplicates",
        action="store_true",
        help="report files with identical contents instead of sorting",
    )
    parser.add_argument(
        "--undo",
        action="store_true",
        help="reverse the most recent run in the folder",
    )
    parser.add_argument(
        "--undo-id",
        metavar="ID",
        help="reverse a specific recorded run (unique id prefix)",
    )
    parser.add_argument(
        "--min-age",
        type=float,
        default=0.0,
        metavar="DAYS",
        help="only sort files older than DAYS (default: all files)",
    )
    parser.add_argument(
        "--on-collision",
        choices=(RENAME, SKIP),
        default=RENAME,
        help="rename a clashing file (default) or skip it",
    )
    parser.add_argument(
        "--prune-empty",
        action="store_true",
        help="remove folders left empty after sorting",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="list recorded runs in the folder",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _payload(
    args: argparse.Namespace,
    moves: Sequence[Move],
    pruned: Sequence[Path] = (),
    skipped: Sequence[Path] = (),
) -> dict[str, Any]:
    return {
        "root": str(args.directory.resolve()),
        "dry_run": bool(args.dry_run),
        "count": len(moves),
        "moves": [
            {"source": _relative(m.source, m.root), "destination": _relative(m.destination, m.root)}
            for m in moves
        ],
        "skipped": [_relative(path, args.directory) for path in skipped],
        "pruned": [_relative(path, args.directory) for path in pruned],
    }


def _report(
    args: argparse.Namespace,
    verb: str,
    moves: Sequence[Move],
    pruned: Sequence[Path] = (),
    skipped: Sequence[Path] = (),
) -> None:
    if args.as_json:
        print(json.dumps(_payload(args, moves, pruned, skipped), indent=2))
        return
    if moves:
        print(f"{verb} {len(moves)} file(s) in {args.directory.resolve()}")
        for move in moves:
            print(f"  {move}")
    if skipped:
        print(f"Skipped {len(skipped)} file(s) whose name already exists.")
    if pruned:
        print(f"Removed {len(pruned)} empty folder(s).")


def _human_size(count: int) -> str:
    value = float(count)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def _run_duplicates(args: argparse.Namespace) -> int:
    try:
        groups = find_duplicates(args.directory, exclude=args.exclude)
    except NotADirectoryError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(
            json.dumps(
                {
                    "root": str(args.directory.resolve()),
                    "groups": [
                        {
                            "size": group.size,
                            "digest": group.digest,
                            "wasted": group.wasted_bytes,
                            "paths": [_relative(path, args.directory) for path in group.paths],
                        }
                        for group in groups
                    ],
                    "wasted": total_wasted(groups),
                },
                indent=2,
            )
        )
        return 0

    if not groups:
        print("No duplicate files found.")
        return 0

    for group in groups:
        print(f"{_human_size(group.size)} each, {len(group.paths)} copies:")
        for path in group.paths:
            print(f"  {path.relative_to(args.directory)}")
    print(f"Total reclaimable: {_human_size(total_wasted(groups))}")
    return 0


def _run_undo(args: argparse.Namespace) -> int:
    try:
        moves = journal.plan_undo(args.directory, args.undo_id)
    except FileNotFoundError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 2

    _report(args, "Would restore" if args.dry_run else "Restored", moves)
    if not args.dry_run:
        journal.undo(args.directory, args.undo_id)
    return 0


def _run_history(args: argparse.Namespace) -> int:
    recorded = list(reversed(journal.runs(args.directory)))

    if args.as_json:
        print(
            json.dumps(
                {
                    "root": str(args.directory.resolve()),
                    "runs": [
                        {"id": run.id, "created": run.created, "moves": run.move_count}
                        for run in recorded
                    ],
                },
                indent=2,
            )
        )
        return 0

    if not recorded:
        print("No recorded runs in this folder.")
        return 0

    for run in recorded:
        print(f"{run.id}  {run.created}  {run.move_count} file(s)")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = build_parser().parse_args(argv)

    if args.history:
        return _run_history(args)

    if args.duplicates:
        return _run_duplicates(args)

    if args.undo_id:
        args.undo = True

    if args.undo:
        return _run_undo(args)

    try:
        result = plan(
            args.directory,
            recursive=args.recursive,
            by=args.by,
            exclude=args.exclude,
            on_collision=args.on_collision,
            min_age_days=args.min_age,
        )
    except NotADirectoryError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 2
    except TidyupError as exc:
        print(f"tidyup: {exc}", file=sys.stderr)
        return 2

    moves = list(result.moves)
    skipped = list(result.skipped)
    pruned: list[Path] = []
    if not args.dry_run:
        if moves:
            journal.save(args.directory, moves)
            apply_moves(moves)
        if args.prune_empty:
            pruned = prune_empty_dirs(args.directory)

    if not moves and not pruned and not skipped:
        if args.as_json:
            print(json.dumps(_payload(args, []), indent=2))
        else:
            print("Nothing to tidy - the folder is already sorted.")
        return 0

    _report(args, "Would move" if args.dry_run else "Moved", moves, pruned, skipped)

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
