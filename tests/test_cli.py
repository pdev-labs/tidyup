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
