"""Planning and applying moves.

Sorting is split into two phases on purpose: :func:`plan_sort` is pure and
returns the exact list of moves, and :func:`apply_moves` is the only function
that touches the filesystem. That keeps ``--dry-run`` honest - it prints the
same plan that a real run would execute.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .categories import FALLBACK, all_categories, category_for

_CATEGORY_DIR_NAMES = frozenset(all_categories())


@dataclass(frozen=True)
class Move:
    """A single file relocation."""

    source: Path
    destination: Path

    def __str__(self) -> str:
        return f"{self.source.name} -> {self.destination.relative_to(self.destination.parents[1])}"


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


def _iter_candidates(root: Path, recursive: bool) -> Iterable[Path]:
    entries = root.rglob("*") if recursive else root.iterdir()
    for entry in entries:
        if not entry.is_file() or entry.is_symlink() or _is_ignored(entry):
            continue
        # A recursive run must not re-sort files that already sit in a
        # category folder, otherwise a second run would chase its own tail.
        if recursive and entry.parent.name in _CATEGORY_DIR_NAMES:
            continue
        yield entry


def plan_sort(root: Path, *, recursive: bool = False) -> list[Move]:
    """Return the moves needed to tidy ``root``, without touching anything.

    Files are grouped by :func:`~tidyup.categories.category_for` into
    ``root/<Category>/<name>``. Existing files are never overwritten: a clash
    produces ``name (1).ext`` instead.

    Raises:
        NotADirectoryError: if ``root`` is not an existing directory.
    """
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    moves: list[Move] = []
    planned: set[Path] = set()

    for path in sorted(_iter_candidates(root, recursive), key=lambda p: p.name.lower()):
        category = category_for(path)
        destination = _unique_destination(root / category / path.name, planned)
        planned.add(destination)
        if destination == path:
            continue
        moves.append(Move(source=path, destination=destination))

    return moves


def apply_moves(moves: Sequence[Move]) -> None:
    """Perform ``moves`` on disk, creating category folders as needed."""
    for move in moves:
        move.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(move.source), str(move.destination))


__all__ = ["Move", "apply_moves", "plan_sort", "FALLBACK"]
