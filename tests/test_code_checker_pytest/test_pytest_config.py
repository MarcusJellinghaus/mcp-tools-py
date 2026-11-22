"""Tests for reading the project's pytest config."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_pytest.pytest_config import (
    DEDICATED_FILES,
    PytestConfig,
    _parse_bool,
    read_pytest_config,
)

_EMPTY = PytestConfig([], [], None, None)


def _write(root: Path, name: str, text: str) -> None:
    """Write *text* to ``root/name``."""
    (root / name).write_text(text, encoding="utf-8")


def _config(root: Path, pyproject: str) -> PytestConfig | None:
    """Write *pyproject* as pyproject.toml and read the config."""
    _write(root, "pyproject.toml", pyproject)
    return read_pytest_config(str(root))


class TestAddopts:
    """Test the ``addopts`` value types per table."""

    def test_ini_string_is_split(self, tmp_path: Path) -> None:
        """A string in ini_options is split like a shell command line."""
        config = _config(
            tmp_path, "[tool.pytest.ini_options]\naddopts = \"-n auto -m 'not slow'\"\n"
        )

        assert config is not None
        assert config.addopts == ["-n", "auto", "-m", "not slow"]

    def test_ini_string_with_bad_quoting_is_empty(self, tmp_path: Path) -> None:
        """A string shlex can't split gives no tokens."""
        config = _config(tmp_path, '[tool.pytest.ini_options]\naddopts = "-m \'x"\n')

        assert config is not None
        assert config.addopts == []

    def test_ini_list(self, tmp_path: Path) -> None:
        """A list in ini_options is taken token by token."""
        config = _config(
            tmp_path, '[tool.pytest.ini_options]\naddopts = ["-m", "not slow"]\n'
        )

        assert config is not None
        assert config.addopts == ["-m", "not slow"]

    def test_native_list(self, tmp_path: Path) -> None:
        """A list in [tool.pytest] is taken token by token."""
        config = _config(tmp_path, '[tool.pytest]\naddopts = ["-n", "auto"]\n')

        assert config is not None
        assert config.addopts == ["-n", "auto"]

    def test_native_string_is_ignored(self, tmp_path: Path) -> None:
        """pytest rejects a string in [tool.pytest], so it gives no tokens."""
        config = _config(tmp_path, '[tool.pytest]\naddopts = "-n auto"\n')

        assert config is not None
        assert config.addopts == []


class TestMarkers:
    """Test the ``markers`` value types and name extraction."""

    def test_ini_list(self, tmp_path: Path) -> None:
        """List entries give the names before ``:`` or ``(``."""
        config = _config(
            tmp_path,
            "[tool.pytest.ini_options]\n"
            'markers = ["slow: desc", "x(arg): d", "integration"]\n',
        )

        assert config is not None
        assert config.markers == ["slow", "x", "integration"]

    def test_ini_multiline_string(self, tmp_path: Path) -> None:
        """A multi-line string is split on lines, skipping blank ones."""
        config = _config(
            tmp_path,
            "[tool.pytest.ini_options]\n"
            'markers = """\n  slow: desc\n\n  x(arg): d\n"""\n',
        )

        assert config is not None
        assert config.markers == ["slow", "x"]

    def test_native_list(self, tmp_path: Path) -> None:
        """A list in [tool.pytest] gives the names."""
        config = _config(tmp_path, '[tool.pytest]\nmarkers = ["slow: desc"]\n')

        assert config is not None
        assert config.markers == ["slow"]

    def test_native_string_is_ignored(self, tmp_path: Path) -> None:
        """[tool.pytest] takes a list only."""
        config = _config(tmp_path, '[tool.pytest]\nmarkers = "slow: desc"\n')

        assert config is not None
        assert config.markers == []


class TestStrictKeys:
    """Test ``strict_markers`` and ``strict`` per table."""

    @pytest.mark.parametrize("value", ["true", "True", "YES", "1", "on", "t", "y"])
    def test_parse_bool_true(self, value: str) -> None:
        """pytest's true spellings, any case."""
        assert _parse_bool(value) is True

    @pytest.mark.parametrize("value", ["false", "FALSE", "no", "0", "off", "f", "n"])
    def test_parse_bool_false(self, value: str) -> None:
        """pytest's false spellings, any case."""
        assert _parse_bool(value) is False

    @pytest.mark.parametrize("value", ["", "maybe", "2", " true"])
    def test_parse_bool_unknown(self, value: str) -> None:
        """Any other text is not a bool."""
        assert _parse_bool(value) is None

    def test_ini_bools(self, tmp_path: Path) -> None:
        """TOML bools in ini_options are taken as-is."""
        config = _config(
            tmp_path,
            "[tool.pytest.ini_options]\nstrict_markers = true\nstrict = false\n",
        )

        assert config is not None
        assert (config.strict_markers, config.strict) == (True, False)

    def test_ini_strings(self, tmp_path: Path) -> None:
        """Strings in ini_options are read as pytest's bool spellings."""
        config = _config(
            tmp_path,
            '[tool.pytest.ini_options]\nstrict_markers = "yes"\nstrict = "Off"\n',
        )

        assert config is not None
        assert (config.strict_markers, config.strict) == (True, False)

    def test_ini_unknown_spelling(self, tmp_path: Path) -> None:
        """An unknown spelling is unset."""
        config = _config(tmp_path, '[tool.pytest.ini_options]\nstrict = "maybe"\n')

        assert config is not None
        assert config.strict is None

    def test_native_bool(self, tmp_path: Path) -> None:
        """A TOML bool in [tool.pytest] is taken."""
        config = _config(tmp_path, "[tool.pytest]\nstrict_markers = true\n")

        assert config is not None
        assert config.strict_markers is True

    def test_native_string_is_ignored(self, tmp_path: Path) -> None:
        """[tool.pytest] takes bools only."""
        config = _config(
            tmp_path, '[tool.pytest]\nstrict_markers = "true"\nstrict = "yes"\n'
        )

        assert config is not None
        assert (config.strict_markers, config.strict) == (None, None)

    def test_unset(self, tmp_path: Path) -> None:
        """Unset keys are None."""
        config = _config(tmp_path, '[tool.pytest.ini_options]\naddopts = "-x"\n')

        assert config is not None
        assert (config.strict_markers, config.strict) == (None, None)


class TestDedicatedFiles:
    """Test the files pytest reads before pyproject.toml."""

    @pytest.mark.parametrize("name", DEDICATED_FILES)
    def test_each_wins_over_pyproject(self, tmp_path: Path, name: str) -> None:
        """Any dedicated file, even empty, is named and nothing else is read."""
        _write(tmp_path, name, "")

        config = _config(
            tmp_path,
            '[tool.pytest.ini_options]\naddopts = "-x"\nmarkers = ["slow"]\n',
        )

        assert config == PytestConfig([], [], None, None, name)

    def test_first_in_order_wins(self, tmp_path: Path) -> None:
        """With several present, the first in pytest's order is named."""
        _write(tmp_path, "pytest.ini", "")
        _write(tmp_path, ".pytest.toml", "")

        config = read_pytest_config(str(tmp_path))

        assert config is not None
        assert config.not_read == ".pytest.toml"


class TestFallbackFiles:
    """Test ``tox.ini`` / ``setup.cfg``, read only without a pyproject section."""

    @pytest.mark.parametrize(
        ("name", "header"), [("tox.ini", "[pytest]"), ("setup.cfg", "[tool:pytest]")]
    )
    def test_without_pyproject_section(
        self, tmp_path: Path, name: str, header: str
    ) -> None:
        """A pytest section there is named when pyproject.toml has none."""
        _write(tmp_path, name, f"[other]\nx = 1\n  {header}  \naddopts = -x\n")

        config = _config(tmp_path, "[tool.black]\nline-length = 88\n")

        assert config == PytestConfig([], [], None, None, name)

    @pytest.mark.parametrize(
        ("name", "header"), [("tox.ini", "[pytest]"), ("setup.cfg", "[tool:pytest]")]
    )
    def test_empty_ini_options_counts_as_section(
        self, tmp_path: Path, name: str, header: str
    ) -> None:
        """An empty [tool.pytest.ini_options] beats the file: no note."""
        _write(tmp_path, name, f"{header}\naddopts = -x\n")

        config = _config(tmp_path, "[tool.pytest.ini_options]\n")

        assert config == _EMPTY

    @pytest.mark.parametrize(
        ("name", "header"), [("tox.ini", "[pytest]"), ("setup.cfg", "[tool:pytest]")]
    )
    def test_empty_native_table_does_not_count(
        self, tmp_path: Path, name: str, header: str
    ) -> None:
        """An empty [tool.pytest] is no section, so the file is named."""
        _write(tmp_path, name, f"{header}\naddopts = -x\n")

        config = _config(tmp_path, "[tool.pytest]\n")

        assert config == PytestConfig([], [], None, None, name)

    def test_tox_ini_without_pytest_section(self, tmp_path: Path) -> None:
        """A tox.ini without [pytest] is no pytest config."""
        _write(tmp_path, "tox.ini", "[tox]\nenvlist = py311\n")

        assert read_pytest_config(str(tmp_path)) == _EMPTY

    def test_tox_ini_without_section_falls_through_to_setup_cfg(
        self, tmp_path: Path
    ) -> None:
        """setup.cfg is still checked after a tox.ini without [pytest]."""
        _write(tmp_path, "tox.ini", "[tox]\n")
        _write(tmp_path, "setup.cfg", "[tool:pytest]\n")

        config = read_pytest_config(str(tmp_path))

        assert config is not None
        assert config.not_read == "setup.cfg"

    def test_only_tox_ini(self, tmp_path: Path) -> None:
        """No pyproject.toml, only tox.ini [pytest]."""
        _write(tmp_path, "tox.ini", "[pytest]\n")

        config = read_pytest_config(str(tmp_path))

        assert config is not None
        assert config.not_read == "tox.ini"

    def test_only_setup_cfg(self, tmp_path: Path) -> None:
        """No pyproject.toml, only setup.cfg [tool:pytest]."""
        _write(tmp_path, "setup.cfg", "[tool:pytest]\n")

        config = read_pytest_config(str(tmp_path))

        assert config is not None
        assert config.not_read == "setup.cfg"


class TestUnreadable:
    """Test the cases that give None, and the empty config."""

    def test_invalid_toml(self, tmp_path: Path) -> None:
        """Invalid TOML gives None instead of raising."""
        assert _config(tmp_path, "[tool.pytest.ini_options\n") is None

    def test_os_error(self, tmp_path: Path) -> None:
        """An OSError while reading pyproject.toml gives None."""
        with patch(
            "mcp_tools_py.code_checker_pytest.pytest_config.read_pyproject_tool_tables",
            side_effect=OSError("denied"),
        ):
            assert read_pytest_config(str(tmp_path)) is None

    def test_both_tables_non_empty(self, tmp_path: Path) -> None:
        """pytest rejects both pytest tables non-empty, so the config is unread."""
        config = _config(
            tmp_path,
            '[tool.pytest]\naddopts = ["-x"]\n\n'
            '[tool.pytest.ini_options]\naddopts = "-v"\n',
        )

        assert config is None

    def test_native_with_empty_ini_options(self, tmp_path: Path) -> None:
        """A non-empty [tool.pytest] next to an empty ini_options is read."""
        config = _config(
            tmp_path,
            '[tool.pytest]\naddopts = ["-x"]\n\n[tool.pytest.ini_options]\n',
        )

        assert config == PytestConfig(["-x"], [], None, None)

    def test_no_pyproject(self, tmp_path: Path) -> None:
        """No pyproject.toml and no other file: an empty config."""
        assert read_pytest_config(str(tmp_path)) == _EMPTY

    def test_pyproject_without_tool_table(self, tmp_path: Path) -> None:
        """A pyproject.toml without [tool]: an empty config."""
        assert _config(tmp_path, '[project]\nname = "x"\n') == _EMPTY


def test_pytest_env_is_scrubbed() -> None:
    """The autouse scrub leaves no PYTEST* variable but PYTEST_CURRENT_TEST."""
    leftover = [
        name
        for name in os.environ
        if name.upper().startswith("PYTEST") and name != "PYTEST_CURRENT_TEST"
    ]

    assert not leftover
