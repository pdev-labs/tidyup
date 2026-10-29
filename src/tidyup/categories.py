"""Extension to category mapping used by the sorter.

The mapping is deliberately plain data: adding a category or an extension is a
one-line change, and the tests assert that no extension appears twice.
"""

from __future__ import annotations

from pathlib import Path

CATEGORIES: dict[str, frozenset[str]] = {
    "Images": frozenset(
        {
            "jpg",
            "jpeg",
            "png",
            "gif",
            "webp",
            "svg",
            "bmp",
            "tif",
            "tiff",
            "heic",
            "heif",
            "avif",
            "raw",
            "cr2",
            "nef",
            "psd",
        }
    ),
    "Documents": frozenset(
        {
            "pdf",
            "doc",
            "docx",
            "odt",
            "rtf",
            "txt",
            "md",
            "epub",
            "mobi",
            "ppt",
            "pptx",
            "odp",
            "xls",
            "xlsx",
            "ods",
            "csv",
            "tsv",
        }
    ),
    "Audio": frozenset({"mp3", "wav", "flac", "aac", "ogg", "oga", "opus", "m4a", "wma", "aiff"}),
    "Video": frozenset({"mp4", "mkv", "mov", "avi", "webm", "wmv", "flv", "m4v", "mpg", "mpeg"}),
    "Archives": frozenset(
        {"zip", "tar", "gz", "tgz", "bz2", "xz", "zst", "7z", "rar", "iso", "dmg"}
    ),
    "Code": frozenset(
        {
            "py",
            "js",
            "mjs",
            "ts",
            "tsx",
            "jsx",
            "go",
            "rs",
            "c",
            "h",
            "cc",
            "cpp",
            "hpp",
            "java",
            "kt",
            "rb",
            "php",
            "sh",
            "bash",
            "zsh",
            "ps1",
            "sql",
            "html",
            "css",
            "scss",
            "json",
            "yaml",
            "yml",
            "toml",
            "ini",
        }
    ),
    "Data": frozenset({"db", "sqlite", "sqlite3", "parquet", "feather", "pkl", "npy", "npz"}),
}

FALLBACK = "Other"

_LOOKUP: dict[str, str] = {
    extension: category for category, extensions in CATEGORIES.items() for extension in extensions
}


def category_for(path: Path) -> str:
    """Return the category folder a file belongs in.

    Files without a suffix, or with a suffix we do not recognise, land in
    ``Other`` rather than being left loose in the directory.
    """
    suffix = path.suffix.lower().lstrip(".")
    if not suffix:
        return FALLBACK
    return _LOOKUP.get(suffix, FALLBACK)


def all_categories() -> tuple[str, ...]:
    """Return every category name, including the fallback, in a stable order."""
    return (*CATEGORIES, FALLBACK)
