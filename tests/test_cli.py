import pytest

from tidyup import __version__
from tidyup.cli import main


def test_version_flag_exits_cleanly(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_no_arguments_is_harmless(capsys):
    assert main([]) == 0
    assert "Nothing to do yet" in capsys.readouterr().err
