import json
from pathlib import Path

import pytest

from tidyup import journal
from tidyup.organizer import Move, plan_sort


def touch(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).write_text("x", encoding="utf-8")


def tidy(tmp_path: Path):
    moves = plan_sort(tmp_path)
    journal.save(tmp_path, moves)
    from tidyup.organizer import apply_moves

    apply_moves(moves)
    return moves


def test_save_writes_a_journal_with_relative_paths(tmp_path):
    touch(tmp_path, "a.jpg")

    path = journal.save(tmp_path, plan_sort(tmp_path))

    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format"] == journal.JOURNAL_FORMAT
    assert payload["moves"] == [{"source": "a.jpg", "destination": "Images/a.jpg"}]


def test_save_refuses_empty_runs(tmp_path):
    with pytest.raises(ValueError):
        journal.save(tmp_path, [])


def test_latest_returns_none_without_journals(tmp_path):
    assert journal.latest(tmp_path) is None


def test_latest_picks_the_newest_journal(tmp_path):
    touch(tmp_path, "a.jpg")
    first = journal.save(tmp_path, plan_sort(tmp_path))
    touch(tmp_path, "b.pdf")
    second = journal.save(tmp_path, plan_sort(tmp_path))

    assert journal.latest(tmp_path) == second
    assert second > first


def test_undo_restores_files_and_removes_empty_folders(tmp_path):
    touch(tmp_path, "a.jpg", "b.pdf")
    tidy(tmp_path)
    assert (tmp_path / "Images" / "a.jpg").exists()

    journal.undo(tmp_path)

    assert (tmp_path / "a.jpg").exists()
    assert (tmp_path / "b.pdf").exists()
    assert not (tmp_path / "Images").exists()
    assert not (tmp_path / "Documents").exists()


def test_undo_renames_when_the_original_name_is_taken_again(tmp_path):
    touch(tmp_path, "a.jpg")
    tidy(tmp_path)
    touch(tmp_path, "a.jpg")  # a new file reuses the old name

    journal.undo(tmp_path)

    assert (tmp_path / "a.jpg").read_text(encoding="utf-8") == "x"
    assert (tmp_path / "a (1).jpg").exists()
    assert not (tmp_path / "Images" / "a.jpg").exists()


def test_undo_without_a_journal_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        journal.plan_undo(tmp_path)


def test_journal_files_are_never_sorted(tmp_path):
    touch(tmp_path, "a.jpg")
    tidy(tmp_path)

    moves = plan_sort(tmp_path, recursive=True)

    assert all(".tidyup" not in str(m.source) for m in moves)


def test_undo_plan_is_pure(tmp_path):
    touch(tmp_path, "a.jpg")
    tidy(tmp_path)

    journal.plan_undo(tmp_path)

    assert (tmp_path / "Images" / "a.jpg").exists()


def test_unsupported_journal_format_is_rejected(tmp_path):
    directory = journal.journal_dir(tmp_path)
    directory.mkdir(parents=True)
    bad = directory / "20260101T000000000000Z.json"
    bad.write_text(json.dumps({"format": 99, "moves": []}), encoding="utf-8")

    with pytest.raises(ValueError):
        journal.load(bad)


def test_move_type_is_importable_for_journal_users():
    assert Move.__name__ == "Move"
