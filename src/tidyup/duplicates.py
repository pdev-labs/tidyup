"""Duplicate detection.

Files are bucketed by size first, so only files that could possibly match are
ever read. Hashing uses BLAKE2b truncated to 16 bytes: collisions are not a
practical concern for this job and it keeps scanning large folders cheap.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .organizer import iter_files

CHUNK_SIZE = 1 << 20


@dataclass(frozen=True)
class DuplicateGroup:
    """Files whose contents are byte-for-byte identical."""

    size: int
    digest: str
    paths: tuple[Path, ...]

    @property
    def wasted_bytes(self) -> int:
        """Bytes that could be reclaimed by keeping one copy."""
        return self.size * (len(self.paths) - 1)


def digest_of(path: Path) -> str:
    """Return a short content hash for ``path``."""
    hasher = hashlib.blake2b(digest_size=16)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_SIZE), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def find_duplicates(
    root: Path,
    *,
    exclude: Sequence[str] = (),
    min_size: int = 1,
) -> list[DuplicateGroup]:
    """Return duplicate groups under ``root``, largest waste first.

    Empty files are skipped by default: a folder full of placeholder files would
    otherwise produce a lot of noise for no reclaimed space.

    Raises:
        NotADirectoryError: if ``root`` is not an existing directory.
    """
    if not root.is_dir():
        raise NotADirectoryError(f"not a directory: {root}")

    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in iter_files(root, recursive=True, exclude=exclude):
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size < min_size:
            continue
        by_size[size].append(path)

    groups: list[DuplicateGroup] = []
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        by_digest: dict[str, list[Path]] = defaultdict(list)
        for path in candidates:
            try:
                by_digest[digest_of(path)].append(path)
            except OSError:
                continue
        for digest, paths in by_digest.items():
            if len(paths) > 1:
                groups.append(DuplicateGroup(size=size, digest=digest, paths=tuple(sorted(paths))))

    groups.sort(key=lambda group: (-group.wasted_bytes, -group.size))
    return groups


def total_wasted(groups: Sequence[DuplicateGroup]) -> int:
    return sum(group.wasted_bytes for group in groups)
