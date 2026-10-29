"""Undo journals.

Every real run records what it did in ``<folder>/.tidyup/journal/<stamp>.json``.
Recording relative paths means the folder can be moved or synced and the
journal keeps working, and keeping it per-folder means no global state to
clean up.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .organizer import STATE_DIRNAME, Move, _unique_destination, apply_moves

JOURNAL_DIRNAME = STATE_DIRNAME
JOURNAL_FORMAT = 1


def journal_dir(root: Path) -> Path:
    return root / JOURNAL_DIRNAME / "journal"


def save(root: Path, moves: Sequence[Move]) -> Path:
    """Write a journal for ``moves`` and return its path."""
    if not moves:
        raise ValueError("refusing to journal an empty run")

    directory = journal_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc)
    path = directory / f"{stamp:%Y%m%dT%H%M%S%fZ}.json"

    payload: dict[str, Any] = {
        "format": JOURNAL_FORMAT,
        "created": stamp.isoformat(),
        "root": str(root.resolve()),
        "moves": [
            {
                "source": _relative(move.source, root),
                "destination": _relative(move.destination, root),
            }
            for move in moves
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def latest(root: Path) -> Path | None:
    """Return the most recent journal for ``root``, if any."""
    directory = journal_dir(root)
    if not directory.is_dir():
        return None
    journals = sorted(directory.glob("*.json"))
    return journals[-1] if journals else None


def load(path: Path) -> list[dict[str, str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("format") != JOURNAL_FORMAT:
        raise ValueError(f"unsupported journal format in {path}")
    return data["moves"]


def plan_undo(root: Path) -> list[Move]:
    """Return the moves that would reverse the most recent run.

    Raises:
        FileNotFoundError: when there is no journal to undo.
    """
    path = latest(root)
    if path is None:
        raise FileNotFoundError(f"no tidyup journal found in {journal_dir(root)}")

    reversed_moves: list[Move] = []
    planned: set[Path] = set()
    for entry in reversed(load(path)):
        source = root / entry["destination"]
        destination = _unique_destination(root / entry["source"], planned)
        planned.add(destination)
        reversed_moves.append(Move(source=source, destination=destination, root=root))
    return reversed_moves


def undo(root: Path) -> list[Move]:
    """Apply the most recent journal to ``root`` and return what was restored."""
    moves = plan_undo(root)
    apply_moves([m for m in moves if m.source.exists()])
    _prune_empty_dirs(root, moves)
    return moves


def _prune_empty_dirs(root: Path, moves: Sequence[Move]) -> None:
    """Remove folders this run created, deepest first, if now empty."""
    parents = {m.source.parent for m in moves}
    for directory in sorted(parents, key=lambda p: len(p.parts), reverse=True):
        while directory != root and root in directory.parents:
            try:
                directory.rmdir()
            except OSError:  # not empty or already gone
                break
            directory = directory.parent
