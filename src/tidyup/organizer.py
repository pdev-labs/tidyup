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
EXTENSION = "extension"

RENAME = "rename"
SKIP = "skip"

#: Folder name used for files without a suffix when grouping by extension.
NO_EXTENSION = "no-extension"

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


def _extension_of(path: Path) -> str:
    return path.suffix.lower().lstrip(".") or NO_EXTENSION


def _destination_dir(path: Path, root: Path, by: str) -> Path:
    if by == DATE:
        stamp = datetime.fromtimestamp(path.stat().st_mtime)
        return root / f"{stamp:%Y}" / f"{stamp:%m}"
    if by == EXTENSION:
        return root / _extension_of(path)
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
    if by == EXTENSION:
        return parent.name == _extension_of(path)
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


def iter_files(
    root: Path,
    *,
    recursive: bool = False,
    by: str = CATEGORY,
    exclude: Sequence[str] = (),
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


@dataclass(frozen=True)
class Plan:
    """The outcome of planning a sort."""

    moves: tuple[Move, ...]
    skipped: tuple[Path, ...] = ()


def plan(
    root: Path,
    *,
    recursive: bool = False,
    by: str = CATEGORY,
    exclude: Sequence[str] = (),
    on_collision: str = RENAME,
) -> Plan:
    """Return the moves needed to tidy ``root``, without touching anything.

    With ``by="category"`` files go to ``root/<Category>/<name>``. With
    ``by="date"`` they go to ``root/<YYYY>/<MM>/<name>`` using modification
    time. With ``by="extension"`` they go to ``root/<ext>/<name>``.

    Existing files are never overwritten. With ``on_collision="rename"`` (the
    default) a clash produces ``name (1).ext``; with ``"skip"`` the file is
    left where it is and reported in :attr:`Plan.skipped`.

    ``exclude`` holds shell globs matched against the path relative to
    ``root`` and against the bare file name; matching files are left in place.

    Raises:
        NotADirectoryError: if ``root`` is not an existing directory.
        TidyupError: if a target folder name is taken by an existing file.
        ValueError: if ``by`` is not a known grouping mode.
    """
    if by not in (CATEGORY, DATE, EXTENSION):
        raise ValueError(f"unknown grouping mode: {by!r}")
    if on_collision not in (RENAME, SKIP):
        raise ValueError(f"unknown collision policy: {on_collision!r}")
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    moves: list[Move] = []
    skipped: list[Path] = []
    planned: set[Path] = set()

    for path in sorted(
        iter_files(root, recursive=recursive, by=by, exclude=exclude),
        key=lambda p: p.name.lower(),
    ):
        target_dir = _destination_dir(path, root, by)
        _check_target_dir(target_dir)
        target = target_dir / path.name
        if on_collision == SKIP and (target in planned or target.exists()):
            skipped.append(path)
            continue
        destination = _unique_destination(target, planned)
        planned.add(destination)
        if destination == path:
            continue
        moves.append(Move(source=path, destination=destination, root=root))

    return Plan(moves=tuple(moves), skipped=tuple(skipped))


def plan_sort(
    root: Path,
    *,
    recursive: bool = False,
    by: str = CATEGORY,
    exclude: Sequence[str] = (),
    on_collision: str = RENAME,
) -> list[Move]:
    """Return just the moves from :func:`plan`."""
    return list(
        plan(
            root,
            recursive=recursive,
            by=by,
            exclude=exclude,
            on_collision=on_collision,
        ).moves
    )


def prune_empty_dirs(root: Path) -> list[Path]:
    """Remove empty directories under ``root``, deepest first.

    State folders (``.tidyup``) are never touched, and a directory that still
    holds anything is left alone. Returns the directories that were removed.
    """
    if not root.is_dir():
        return []

    removed: list[Path] = []
    directories = [p for p in root.rglob("*") if p.is_dir() and not p.is_symlink()]
    for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True):
        if STATE_DIRNAME in directory.relative_to(root).parts:
            continue
        try:
            directory.rmdir()
        except OSError:
            continue
        removed.append(directory)
    return removed


def apply_moves(moves: Sequence[Move]) -> None:
    """Perform ``moves`` on disk, creating target folders as needed."""
    for move in moves:
        move.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(move.source), str(move.destination))


__all__ = [
    "CATEGORY",
    "DATE",
    "EXTENSION",
    "NO_EXTENSION",
    "Plan",
    "RENAME",
    "SKIP",
    "Move",
    "TidyupError",
    "apply_moves",
    "iter_files",
    "plan",
    "plan_sort",
    "prune_empty_dirs",
    "FALLBACK",
]
