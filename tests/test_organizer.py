from pathlib import Path

import pytest

from tidyup.categories import CATEGORIES, all_categories, category_for
from tidyup.organizer import DATE, Move, apply_moves, plan_sort


def touch(directory: Path, *names: str) -> None:
    for name in names:
        (directory / name).write_text("x", encoding="utf-8")


def test_category_for_known_extensions():
    assert category_for(Path("photo.JPG")) == "Images"
    assert category_for(Path("report.pdf")) == "Documents"
    assert category_for(Path("song.flac")) == "Audio"
    assert category_for(Path("clip.mkv")) == "Video"
    assert category_for(Path("backup.tar.gz")) == "Archives"


def test_category_for_unknown_or_missing_suffix_falls_back():
    assert category_for(Path("LICENSE")) == "Other"
    assert category_for(Path("weird.qqq")) == "Other"


def test_no_extension_is_registered_twice():
    seen: dict[str, str] = {}
    for category, extensions in CATEGORIES.items():
        for extension in extensions:
            assert extension not in seen, f"{extension} in {seen.get(extension)} and {category}"
            seen[extension] = category


def test_all_categories_includes_fallback():
    assert all_categories()[-1] == "Other"


def test_plan_groups_by_category(tmp_path):
    touch(tmp_path, "a.jpg", "b.pdf", "c.mp3", "notes.qqq")

    moves = plan_sort(tmp_path)

    mapping = {m.source.name: m.destination.parent.name for m in moves}
    assert mapping == {
        "a.jpg": "Images",
        "b.pdf": "Documents",
        "c.mp3": "Audio",
        "notes.qqq": "Other",
    }


def test_plan_is_pure(tmp_path):
    touch(tmp_path, "a.jpg")

    plan_sort(tmp_path)

    assert (tmp_path / "a.jpg").exists()
    assert not (tmp_path / "Images").exists()


def test_collisions_are_renamed_not_overwritten(tmp_path):
    touch(tmp_path, "a.jpg")
    (tmp_path / "Images").mkdir()
    (tmp_path / "Images" / "a.jpg").write_text("original", encoding="utf-8")

    moves = plan_sort(tmp_path)

    assert len(moves) == 1
    assert moves[0].destination.name == "a (1).jpg"
    assert (tmp_path / "Images" / "a.jpg").read_text(encoding="utf-8") == "original"


def test_collisions_within_one_run_do_not_clash(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    (tmp_path / "one" / "a.jpg").write_text("1", encoding="utf-8")
    (tmp_path / "two" / "a.jpg").write_text("2", encoding="utf-8")

    moves = plan_sort(tmp_path, recursive=True)
    destinations = [m.destination for m in moves]

    assert len(set(destinations)) == 2


def test_dotfiles_and_partial_downloads_are_skipped(tmp_path):
    touch(tmp_path, ".hidden", "movie.mp4.part", "real.mp4")

    moves = plan_sort(tmp_path)

    assert [m.source.name for m in moves] == ["real.mp4"]


def test_apply_moves_creates_folders_and_moves_files(tmp_path):
    touch(tmp_path, "a.jpg", "b.pdf")
    moves = plan_sort(tmp_path)

    apply_moves(moves)

    assert (tmp_path / "Images" / "a.jpg").exists()
    assert (tmp_path / "Documents" / "b.pdf").exists()
    assert not (tmp_path / "a.jpg").exists()


def test_plan_on_missing_directory_raises(tmp_path):
    with pytest.raises(NotADirectoryError):
        plan_sort(tmp_path / "nope")


def test_move_str_is_readable(tmp_path):
    move = Move(
        source=tmp_path / "a.jpg",
        destination=tmp_path / "Images" / "a.jpg",
        root=tmp_path,
    )
    assert "a.jpg -> Images/a.jpg" == str(move)


def test_unknown_grouping_mode_raises(tmp_path):
    with pytest.raises(ValueError):
        plan_sort(tmp_path, by="size")


def test_date_mode_groups_by_year_and_month(tmp_path):
    import os
    from datetime import datetime

    photo = tmp_path / "photo.jpg"
    photo.write_text("x", encoding="utf-8")
    stamp = datetime(2021, 3, 15, 12, 0).timestamp()
    os.utime(photo, (stamp, stamp))

    moves = plan_sort(tmp_path, by=DATE)

    assert moves[0].destination == tmp_path / "2021" / "03" / "photo.jpg"


def test_date_mode_recursive_does_not_resort_existing_structure(tmp_path):
    nested = tmp_path / "2021" / "03"
    nested.mkdir(parents=True)
    (nested / "old.jpg").write_text("x", encoding="utf-8")
    (tmp_path / "new.jpg").write_text("x", encoding="utf-8")

    moves = plan_sort(tmp_path, recursive=True, by=DATE)

    assert [m.source.name for m in moves] == ["new.jpg"]
