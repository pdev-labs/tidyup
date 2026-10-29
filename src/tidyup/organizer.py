"""Planning and applying moves.

Sorting is split into two phases on purpose: :func:`plan_sort` is pure and
returns the exact list of moves, and :func:`apply_moves` is the only function
that touches the filesystem. That keeps ``--dry-run`` honest - it prints the
same plan that a real run would execute.
"""

from __future__ import annotations

import fnmatch
import shutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .categories import FALLBACK, all_categories, category_for

CATEGORY = "category"
DATE = "date"

#: Folder where tidyup keeps its own state (undo journals).
STATE_DIRNAME = ".tidyup"

_CATEGORY_DIR_NAMES = frozenset(all_categories())


class TidyupError(Exception):
    """A problem tidyup can explain to the user, rather than a crash."""


@dataclass(frozen=True)
class Move:
    """A single file relocation, relative to the folder being tidied."""

    source: Path
    destination: Path
    root: Path

    def __str__(self) -> str:
        return f"{self.source.name} -> {self.destination.relative_to(self.root)}"


def _is_ignored(path: Path) -> bool:
    """Skip dotfiles and partial downloads; moving them surprises people."""
    return path.name.startswith(".") or path.name.endswith((".part", ".crdownload", ".tmp"))


def _unique_destination(destination: Path, planned: set[Path]) -> Path:
    """Return a free path, renaming instead of overwriting.

    ``planned`` holds destinations already claimed in this run, which are not
    yet on disk during a dry run.
    """
    if destination not in planned and not destination.exists():
        return destination

    stem, suffix = destination.stem, destination.suffix
    counter = 1
    while True:
        candidate = destination.with_name(f"{stem} ({counter}){suffix}")
        if candidate not in planned and not candidate.exists():
            return candidate
        counter += 1


def _destination_dir(path: Path, root: Path, by: str) -> Path:
    if by == DATE:
        stamp = datetime.fromtimestamp(path.stat().st_mtime)
        return root / f"{stamp:%Y}" / f"{stamp:%m}"
    return root / category_for(path)


def _check_target_dir(directory: Path) -> None:
    """Fail early and clearly when a target folder name is taken by a file."""
    if directory.exists() and not directory.is_dir():
        raise TidyupError(
            f"cannot use {directory.name!r} as a folder: a file with that name already exists"
        )


def _already_sorted(path: Path, root: Path, by: str) -> bool:
    """True when the file already lives in a folder this tool would pick."""
    parent = path.parent
    if parent == root:
        return False
    if by == DATE:
        return (
            parent.name.isdigit()
            and len(parent.name) == 2
            and parent.parent.name.isdigit()
            and len(parent.parent.name) == 4
        )
    return parent.name in _CATEGORY_DIR_NAMES


def _excluded(path: Path, root: Path, patterns: Sequence[str]) -> bool:
    """True when ``path`` matches any exclude pattern.

    Patterns are shell globs matched against the path relative to the folder
    being tidied (``node_modules/*``) and against the bare file name
    (``*.log``). Excluding a directory means passing ``dir/*``.
    """
    if not patterns:
        return False
    relative = path.relative_to(root).as_posix()
    return any(
        fnmatch.fnmatchcase(relative, pattern) or fnmatch.fnmatchcase(path.name, pattern)
        for pattern in patterns
    )


def _iter_candidates(
    root: Path, recursive: bool, by: str, exclude: Sequence[str]
) -> Iterable[Path]:
    entries = root.rglob("*") if recursive else root.iterdir()
    for entry in entries:
        if not entry.is_file() or entry.is_symlink() or _is_ignored(entry):
            continue
        if STATE_DIRNAME in entry.relative_to(root).parts[:-1]:
            continue
        if _excluded(entry, root, exclude):
            continue
        # A recursive run must not re-sort files that already sit where this
        # tool would put them, otherwise a second run would chase its own tail.
        if recursive and _already_sorted(entry, root, by):
            continue
        yield entry


def plan_sort(
    root: Path,
    *,
    recursive: bool = False,
    by: str = CATEGORY,
    exclude: Sequence[str] = (),
) -> list[Move]:
    """Return the moves needed to tidy ``root``, without touching anything.

    With ``by="category"`` files go to ``root/<Category>/<name>``. With
    ``by="date"`` they go to ``root/<YYYY>/<MM>/<name>`` using modification
    time. Existing files are never overwritten: a clash produces
    ``name (1).ext`` instead.

    ``exclude`` holds shell globs matched against the path relative to
    ``root`` and against the bare file name; matching files are left in place.

    Raises:
        NotADirectoryError: if ``root`` is not an existing directory.
        TidyupError: if a target folder name is taken by an existing file.
        ValueError: if ``by`` is not a known grouping mode.
    """
    if by not in (CATEGORY, DATE):
        raise ValueError(f"unknown grouping mode: {by!r}")
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    moves: list[Move] = []
    planned: set[Path] = set()

    for path in sorted(
        _iter_candidates(root, recursive, by, exclude), key=lambda p: p.name.lower()
    ):
        target_dir = _destination_dir(path, root, by)
        _check_target_dir(target_dir)
        destination = _unique_destination(target_dir / path.name, planned)
        planned.add(destination)
        if destination == path:
            continue
        moves.append(Move(source=path, destination=destination, root=root))

    return moves


def apply_moves(moves: Sequence[Move]) -> None:
    """Perform ``moves`` on disk, creating target folders as needed."""
    for move in moves:
        move.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(move.source), str(move.destination))


__all__ = [
    "CATEGORY",
    "DATE",
    "Move",
    "TidyupError",
    "apply_moves",
    "plan_sort",
    "FALLBACK",
]
