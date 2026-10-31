"""Per-folder configuration from ``.tidyup.toml``.

A config file keeps the common flags out of shell history: a folder that always
wants date grouping can say so once. Command-line flags always win over the
file, so a one-off run is never blocked by a stale config.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 only
    import tomli as tomllib

from .organizer import CATEGORY, DATE, EXTENSION, RENAME, SKIP

CONFIG_FILENAME = ".tidyup.toml"

_KNOWN_KEYS = frozenset({"by", "recursive", "exclude", "on_collision", "min_age", "prune_empty"})
_BY_VALUES = (CATEGORY, DATE, EXTENSION)
_COLLISION_VALUES = (RENAME, SKIP)


class ConfigError(Exception):
    """A config file tidyup cannot use."""


@dataclass(frozen=True)
class Config:
    """Values read from ``.tidyup.toml``; ``None`` means "not set"."""

    by: str | None = None
    recursive: bool | None = None
    exclude: tuple[str, ...] = ()
    on_collision: str | None = None
    min_age: float | None = None
    prune_empty: bool | None = None


def load(root: Path) -> Config:
    """Read ``root/.tidyup.toml``, or return an empty config if absent.

    Raises:
        ConfigError: for unreadable TOML, unknown keys or invalid values.
    """
    path = root / CONFIG_FILENAME
    if not path.is_file():
        return Config()

    try:
        data: dict[str, Any] = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        raise ConfigError(f"cannot read {CONFIG_FILENAME}: {exc}") from exc

    unknown = set(data) - _KNOWN_KEYS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigError(f"unknown key(s) in {CONFIG_FILENAME}: {names}")

    by = data.get("by")
    if by is not None and by not in _BY_VALUES:
        raise ConfigError(f"{CONFIG_FILENAME}: by must be one of {', '.join(_BY_VALUES)}")

    on_collision = data.get("on_collision")
    if on_collision is not None and on_collision not in _COLLISION_VALUES:
        raise ConfigError(
            f"{CONFIG_FILENAME}: on_collision must be one of {', '.join(_COLLISION_VALUES)}"
        )

    exclude = data.get("exclude", [])
    if not isinstance(exclude, list) or not all(isinstance(item, str) for item in exclude):
        raise ConfigError(f"{CONFIG_FILENAME}: exclude must be a list of globs")

    min_age = data.get("min_age")
    if min_age is not None and (not isinstance(min_age, int | float) or min_age < 0):
        raise ConfigError(f"{CONFIG_FILENAME}: min_age must be a non-negative number")

    return Config(
        by=by,
        recursive=data.get("recursive"),
        exclude=tuple(exclude),
        on_collision=on_collision,
        min_age=float(min_age) if min_age is not None else None,
        prune_empty=data.get("prune_empty"),
    )
