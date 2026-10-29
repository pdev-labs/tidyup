from pathlib import Path

import pytest

from tidyup.duplicates import digest_of, find_duplicates, total_wasted


def write(directory: Path, name: str, content: str) -> Path:
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_identical_files_form_one_group(tmp_path):
    write(tmp_path, "a.txt", "hello")
    write(tmp_path, "b.txt", "hello")
    write(tmp_path, "c.txt", "different")

    groups = find_duplicates(tmp_path)

    assert len(groups) == 1
    assert [p.name for p in groups[0].paths] == ["a.txt", "b.txt"]
    assert groups[0].size == 5


def test_same_size_different_content_is_not_a_duplicate(tmp_path):
    write(tmp_path, "a.txt", "abcde")
    write(tmp_path, "b.txt", "fghij")

    assert find_duplicates(tmp_path) == []


def test_nested_files_are_scanned(tmp_path):
    write(tmp_path, "a.txt", "same")
    write(tmp_path, "deep/nested/b.txt", "same")

    groups = find_duplicates(tmp_path)

    assert len(groups) == 1
    assert len(groups[0].paths) == 2


def test_empty_files_are_skipped_by_default(tmp_path):
    write(tmp_path, "a.txt", "")
    write(tmp_path, "b.txt", "")

    assert find_duplicates(tmp_path) == []


def test_empty_files_can_be_included_explicitly(tmp_path):
    write(tmp_path, "a.txt", "")
    write(tmp_path, "b.txt", "")

    groups = find_duplicates(tmp_path, min_size=0)

    assert len(groups) == 1
    assert groups[0].wasted_bytes == 0


def test_exclude_patterns_are_honoured(tmp_path):
    write(tmp_path, "a.txt", "same")
    write(tmp_path, "b.txt", "same")
    write(tmp_path, "skip.txt", "same")

    groups = find_duplicates(tmp_path, exclude=["skip.txt"])

    assert [p.name for p in groups[0].paths] == ["a.txt", "b.txt"]


def test_wasted_bytes_counts_all_but_one_copy(tmp_path):
    write(tmp_path, "a.txt", "x" * 100)
    write(tmp_path, "b.txt", "x" * 100)
    write(tmp_path, "c.txt", "x" * 100)

    groups = find_duplicates(tmp_path)

    assert groups[0].wasted_bytes == 200
    assert total_wasted(groups) == 200


def test_groups_are_ordered_by_reclaimable_space(tmp_path):
    write(tmp_path, "small-1.txt", "ab")
    write(tmp_path, "small-2.txt", "ab")
    write(tmp_path, "big-1.txt", "y" * 4096)
    write(tmp_path, "big-2.txt", "y" * 4096)

    groups = find_duplicates(tmp_path)

    assert groups[0].size == 4096


def test_digest_is_stable_and_content_sensitive(tmp_path):
    a = write(tmp_path, "a.txt", "hello")
    b = write(tmp_path, "b.txt", "hello")
    c = write(tmp_path, "c.txt", "hello!")

    assert digest_of(a) == digest_of(b)
    assert digest_of(a) != digest_of(c)


def test_missing_directory_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        find_duplicates(tmp_path / "nope")


def test_symlinks_are_not_followed(tmp_path):
    write(tmp_path, "real.txt", "data")
    (tmp_path / "link.txt").symlink_to(tmp_path / "real.txt")

    assert find_duplicates(tmp_path) == []
