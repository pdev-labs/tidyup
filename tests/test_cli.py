import json
from pathlib import Path

import pytest

from tidyup import __version__
from tidyup.cli import main


def touch(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).write_text("x", encoding="utf-8")


def test_version_flag_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_dry_run_prints_plan_and_moves_nothing(tmp_path, capsys):
    touch(tmp_path, "a.jpg")

    assert main([str(tmp_path), "--dry-run"]) == 0

    out = capsys.readouterr().out
    assert "Would move 1 file(s)" in out
    assert "a.jpg -> Images/a.jpg" in out
    assert (tmp_path / "a.jpg").exists()


def test_real_run_moves_files(tmp_path, capsys):
    touch(tmp_path, "a.jpg", "b.pdf")

    assert main([str(tmp_path)]) == 0

    assert "Moved 2 file(s)" in capsys.readouterr().out
    assert (tmp_path / "Images" / "a.jpg").exists()
    assert (tmp_path / "Documents" / "b.pdf").exists()


def test_empty_directory_reports_nothing_to_do(tmp_path, capsys):
    assert main([str(tmp_path)]) == 0
    assert "already sorted" in capsys.readouterr().out


def test_missing_directory_exits_with_code_two(tmp_path, capsys):
    assert main([str(tmp_path / "nope")]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_recursive_flag_reaches_nested_files(tmp_path, capsys):
    (tmp_path / "nested").mkdir()
    touch(tmp_path / "nested", "deep.jpg")

    assert main([str(tmp_path), "-r"]) == 0

    assert (tmp_path / "Images" / "deep.jpg").exists()


def test_by_date_groups_into_year_and_month(tmp_path, capsys):
    import os
    from datetime import datetime

    photo = tmp_path / "photo.jpg"
    photo.write_text("x", encoding="utf-8")
    stamp = datetime(2022, 7, 1, 9, 0).timestamp()
    os.utime(photo, (stamp, stamp))

    assert main([str(tmp_path), "--by", "date"]) == 0

    assert "photo.jpg -> 2022/07/photo.jpg" in capsys.readouterr().out
    assert (tmp_path / "2022" / "07" / "photo.jpg").exists()


def test_invalid_grouping_mode_is_rejected_by_the_parser(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path), "--by", "size"])

    assert exc.value.code == 2


def test_dry_run_writes_no_journal(tmp_path):
    touch(tmp_path, "a.jpg")

    main([str(tmp_path), "--dry-run"])

    assert not (tmp_path / ".tidyup").exists()


def test_real_run_writes_a_journal(tmp_path):
    touch(tmp_path, "a.jpg")

    main([str(tmp_path)])

    assert list((tmp_path / ".tidyup" / "journal").glob("*.json"))


def test_undo_restores_the_last_run(tmp_path, capsys):
    touch(tmp_path, "a.jpg")
    main([str(tmp_path)])

    assert main([str(tmp_path), "--undo"]) == 0

    assert "Restored 1 file(s)" in capsys.readouterr().out
    assert (tmp_path / "a.jpg").exists()
    assert not (tmp_path / "Images").exists()


def test_undo_dry_run_leaves_everything_in_place(tmp_path, capsys):
    touch(tmp_path, "a.jpg")
    main([str(tmp_path)])

    assert main([str(tmp_path), "--undo", "--dry-run"]) == 0

    assert "Would restore 1 file(s)" in capsys.readouterr().out
    assert (tmp_path / "Images" / "a.jpg").exists()


def test_undo_without_a_journal_exits_one(tmp_path, capsys):
    assert main([str(tmp_path), "--undo"]) == 1
    assert "no tidyup journal" in capsys.readouterr().err


def test_folder_name_taken_by_a_file_is_a_clean_error(tmp_path, capsys):
    touch(tmp_path, "a.jpg")
    (tmp_path / "Images").write_text("not a folder", encoding="utf-8")

    assert main([str(tmp_path)]) == 2

    err = capsys.readouterr().err
    assert "Images" in err
    assert "Traceback" not in err
    assert (tmp_path / "a.jpg").exists()


def test_exclude_flag_is_repeatable(tmp_path, capsys):
    touch(tmp_path, "a.jpg", "b.log", "c.bak")

    assert main([str(tmp_path), "-x", "*.log", "-x", "*.bak"]) == 0

    assert "Moved 1 file(s)" in capsys.readouterr().out
    assert (tmp_path / "Images" / "a.jpg").exists()
    assert (tmp_path / "b.log").exists()
    assert (tmp_path / "c.bak").exists()


def test_json_dry_run_is_machine_readable(tmp_path, capsys):
    touch(tmp_path, "a.jpg", "b.pdf")

    assert main([str(tmp_path), "--dry-run", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True
    assert payload["count"] == 2
    assert payload["moves"] == [
        {"source": "a.jpg", "destination": "Images/a.jpg"},
        {"source": "b.pdf", "destination": "Documents/b.pdf"},
    ]
    assert (tmp_path / "a.jpg").exists()


def test_json_real_run_marks_dry_run_false(tmp_path, capsys):
    touch(tmp_path, "a.jpg")

    assert main([str(tmp_path), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is False
    assert (tmp_path / "Images" / "a.jpg").exists()


def test_json_on_a_sorted_folder_is_an_empty_plan(tmp_path, capsys):
    assert main([str(tmp_path), "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["count"] == 0
    assert payload["moves"] == []


def test_json_undo_is_machine_readable(tmp_path, capsys):
    touch(tmp_path, "a.jpg")
    main([str(tmp_path)])
    capsys.readouterr()

    assert main([str(tmp_path), "--undo", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["moves"] == [{"source": "Images/a.jpg", "destination": "a.jpg"}]
    assert (tmp_path / "a.jpg").exists()
