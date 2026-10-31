import pytest

from tidyup.config import Config, ConfigError, load


def write_config(tmp_path, body: str):
    (tmp_path / ".tidyup.toml").write_text(body, encoding="utf-8")


def test_missing_config_leaves_everything_unset(tmp_path):
    assert load(tmp_path) == Config()


def test_reads_every_supported_key(tmp_path):
    write_config(
        tmp_path,
        'by = "date"\nrecursive = true\nexclude = ["*.log", "*.bak"]\n'
        'on_collision = "skip"\nmin_age = 3\nprune_empty = true\n',
    )

    config = load(tmp_path)

    assert config.by == "date"
    assert config.recursive is True
    assert config.exclude == ("*.log", "*.bak")
    assert config.on_collision == "skip"
    assert config.min_age == 3.0
    assert config.prune_empty is True


def test_unknown_key_is_rejected(tmp_path):
    write_config(tmp_path, 'sort_by = "date"\n')

    with pytest.raises(ConfigError, match="unknown key"):
        load(tmp_path)


def test_invalid_grouping_mode_is_rejected(tmp_path):
    write_config(tmp_path, 'by = "size"\n')

    with pytest.raises(ConfigError, match="by must be one of"):
        load(tmp_path)


def test_invalid_collision_policy_is_rejected(tmp_path):
    write_config(tmp_path, 'on_collision = "overwrite"\n')

    with pytest.raises(ConfigError, match="on_collision must be one of"):
        load(tmp_path)


def test_exclude_must_be_a_list_of_strings(tmp_path):
    write_config(tmp_path, 'exclude = "*.log"\n')

    with pytest.raises(ConfigError, match="list of globs"):
        load(tmp_path)


def test_negative_min_age_is_rejected(tmp_path):
    write_config(tmp_path, "min_age = -1\n")

    with pytest.raises(ConfigError, match="non-negative"):
        load(tmp_path)


def test_malformed_toml_is_reported(tmp_path):
    write_config(tmp_path, "by = \n")

    with pytest.raises(ConfigError, match="cannot read"):
        load(tmp_path)
