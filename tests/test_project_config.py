"""Tests for utils.project_config module."""

import logging
import os
import textwrap

import pytest

from mcp_tools_py.utils.project_config import (
    DEFAULT_CHECK_TIMEOUT,
    DEFAULT_PYTEST_TIMEOUT,
    check_line_length_conflicts,
    get_check_timeout,
    get_target_directories,
    resolve_target_directories,
    validate_timeout,
)


class TestGetTargetDirectories:
    """Tests for the get_target_directories function."""

    def test_reads_source_dirs_from_pyproject(self, tmp_path: object) -> None:
        """Source dirs read from [tool.setuptools.packages.find] where."""
        path = str(tmp_path)
        os.makedirs(os.path.join(path, "src"))
        os.makedirs(os.path.join(path, "tests"))
        pyproject = textwrap.dedent("""\
            [tool.setuptools.packages.find]
            where = ["src"]

            [tool.pytest.ini_options]
            testpaths = ["tests"]
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = get_target_directories(path)

        assert "src" in result.directories
        assert result.warnings == []

    def test_reads_test_dirs_from_pyproject(self, tmp_path: object) -> None:
        """Test dirs read from [tool.pytest.ini_options] testpaths."""
        path = str(tmp_path)
        os.makedirs(os.path.join(path, "src"))
        os.makedirs(os.path.join(path, "tests"))
        pyproject = textwrap.dedent("""\
            [tool.setuptools.packages.find]
            where = ["src"]

            [tool.pytest.ini_options]
            testpaths = ["tests"]
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = get_target_directories(path)

        assert "tests" in result.directories
        assert result.warnings == []

    def test_fallback_source_dirs_with_warning(self, tmp_path: object) -> None:
        """Missing setuptools section defaults to ['src'] with warning."""
        path = str(tmp_path)
        os.makedirs(os.path.join(path, "src"))
        os.makedirs(os.path.join(path, "tests"))
        pyproject = textwrap.dedent("""\
            [tool.pytest.ini_options]
            testpaths = ["tests"]
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = get_target_directories(path)

        assert "src" in result.directories
        assert len(result.warnings) == 1
        assert "setuptools" in result.warnings[0]

    def test_fallback_test_dirs_with_warning(self, tmp_path: object) -> None:
        """Missing pytest section defaults to ['tests'] with warning."""
        path = str(tmp_path)
        os.makedirs(os.path.join(path, "src"))
        os.makedirs(os.path.join(path, "tests"))
        pyproject = textwrap.dedent("""\
            [tool.setuptools.packages.find]
            where = ["src"]
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = get_target_directories(path)

        assert "tests" in result.directories
        assert len(result.warnings) == 1
        assert "pytest" in result.warnings[0]

    def test_skips_nonexistent_dirs_silently(self, tmp_path: object) -> None:
        """Dirs that don't exist on disk are filtered out."""
        path = str(tmp_path)
        os.makedirs(os.path.join(path, "src"))
        # "tests" dir intentionally NOT created
        pyproject = textwrap.dedent("""\
            [tool.setuptools.packages.find]
            where = ["src"]

            [tool.pytest.ini_options]
            testpaths = ["tests"]
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = get_target_directories(path)

        assert result.directories == ["src"]
        assert result.warnings == []

    def test_raises_when_no_dirs_exist(self, tmp_path: object) -> None:
        """ValueError raised when none of the resolved dirs exist on disk."""
        path = str(tmp_path)
        # Neither "src" nor "tests" created
        pyproject = textwrap.dedent("""\
            [tool.setuptools.packages.find]
            where = ["src"]

            [tool.pytest.ini_options]
            testpaths = ["tests"]
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        with pytest.raises(ValueError, match="No target directories found"):
            get_target_directories(path)

    def test_missing_pyproject_uses_all_fallbacks(self, tmp_path: object) -> None:
        """No pyproject.toml file uses both fallbacks with both warnings."""
        path = str(tmp_path)
        os.makedirs(os.path.join(path, "src"))
        os.makedirs(os.path.join(path, "tests"))
        # No pyproject.toml written

        result = get_target_directories(path)

        assert "src" in result.directories
        assert "tests" in result.directories
        assert len(result.warnings) == 2
        assert "setuptools" in result.warnings[0]
        assert "pytest" in result.warnings[1]

    def test_malformed_pyproject_raises_valueerror(self, tmp_path: object) -> None:
        """Invalid TOML content raises ValueError, not TOMLDecodeError."""
        path = str(tmp_path)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write("invalid toml {{{{")

        with pytest.raises(ValueError, match="Invalid pyproject.toml"):
            get_target_directories(path)


class TestResolveTargetDirectories:
    """Tests for the resolve_target_directories function."""

    def test_explicit_dirs_returned_as_is(self, tmp_path: object) -> None:
        """When target_directories is provided, returns it without lookup."""
        path = str(tmp_path)
        result = resolve_target_directories(path, ["custom"])
        assert result == ["custom"]

    def test_auto_detects_from_pyproject(self, tmp_path: object) -> None:
        """When target_directories=None, resolves from pyproject.toml."""
        path = str(tmp_path)
        os.makedirs(os.path.join(path, "src"))
        os.makedirs(os.path.join(path, "tests"))
        pyproject = textwrap.dedent("""\
            [tool.setuptools.packages.find]
            where = ["src"]

            [tool.pytest.ini_options]
            testpaths = ["tests"]
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = resolve_target_directories(path, None)

        assert isinstance(result, list)
        assert "src" in result
        assert "tests" in result

    def test_logs_fallback_warnings(
        self, tmp_path: object, caplog: pytest.LogCaptureFixture
    ) -> None:
        """When pyproject.toml has no setuptools section, warnings are logged."""
        path = str(tmp_path)
        os.makedirs(os.path.join(path, "src"))
        os.makedirs(os.path.join(path, "tests"))
        # No pyproject.toml — triggers both fallback warnings

        with caplog.at_level(
            logging.WARNING, logger="mcp_tools_py.utils.project_config"
        ):
            result = resolve_target_directories(path, None)

        assert isinstance(result, list)
        assert len(caplog.records) >= 1
        assert any("setuptools" in r.message for r in caplog.records)

    def test_returns_error_string_on_valueerror(self, tmp_path: object) -> None:
        """When no directories exist on disk, returns an error string."""
        path = str(tmp_path)
        pyproject = textwrap.dedent("""\
            [tool.setuptools.packages.find]
            where = ["src"]

            [tool.pytest.ini_options]
            testpaths = ["tests"]
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = resolve_target_directories(path, None)

        assert isinstance(result, str)
        assert result.startswith("Error resolving target directories:")


class TestCheckLineLengthConflicts:
    """Tests for the check_line_length_conflicts function."""

    def test_all_match_no_warnings(self, tmp_path: object) -> None:
        """All tools set to same line-length → no warnings."""
        path = str(tmp_path)
        pyproject = textwrap.dedent("""\
            [tool.black]
            line-length = 88

            [tool.isort]
            line_length = 88

            [tool.ruff]
            line-length = 88
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = check_line_length_conflicts(path, ["isort", "black"])
        assert result == []

    def test_mismatch_returns_warning(self, tmp_path: object) -> None:
        """black=88, isort=120 → warning string."""
        path = str(tmp_path)
        pyproject = textwrap.dedent("""\
            [tool.black]
            line-length = 88

            [tool.isort]
            line_length = 120
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = check_line_length_conflicts(path, ["isort", "black"])
        assert len(result) == 1
        assert "mismatch" in result[0].lower()
        assert "black=88" in result[0]
        assert "isort=120" in result[0]

    def test_unconfigured_unused_tool_skipped(self, tmp_path: object) -> None:
        """Ruff not configured and not in used_tools → no warning about ruff."""
        path = str(tmp_path)
        pyproject = textwrap.dedent("""\
            [tool.black]
            line-length = 88

            [tool.isort]
            line_length = 88
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = check_line_length_conflicts(path, ["isort", "black"])
        assert result == []

    def test_unconfigured_used_tool_defaults_to_88(self, tmp_path: object) -> None:
        """isort not configured but in used_tools → treated as 88."""
        path = str(tmp_path)
        pyproject = textwrap.dedent("""\
            [tool.black]
            line-length = 120
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = check_line_length_conflicts(path, ["isort", "black"])
        assert len(result) == 1
        assert "isort=88" in result[0]
        assert "black=120" in result[0]

    def test_no_pyproject_no_warnings(self, tmp_path: object) -> None:
        """No pyproject.toml → no warnings."""
        path = str(tmp_path)
        result = check_line_length_conflicts(path, ["isort", "black"])
        assert result == []

    def test_only_one_tool_configured_no_comparison(self, tmp_path: object) -> None:
        """Only one tool value → nothing to compare → no warnings."""
        path = str(tmp_path)
        pyproject = textwrap.dedent("""\
            [tool.black]
            line-length = 88
        """)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write(pyproject)

        result = check_line_length_conflicts(path, ["black"])
        assert result == []


class TestValidateTimeout:
    """Tests for the validate_timeout function."""

    def test_returns_positive_int(self) -> None:
        """A positive integer is returned unchanged."""
        assert validate_timeout(45, "timeout_seconds") == 45

    @pytest.mark.parametrize("value", [0, -1])
    def test_rejects_non_positive(self, value: int) -> None:
        """Zero and negative values raise ValueError naming the source."""
        with pytest.raises(ValueError, match="timeout_seconds"):
            validate_timeout(value, "timeout_seconds")

    @pytest.mark.parametrize("value", ["600", True, 1.5, None])
    def test_rejects_non_int(self, value: object) -> None:
        """Non-int values — including bool — raise ValueError."""
        with pytest.raises(ValueError, match="positive integer"):
            validate_timeout(value, "timeout_seconds")


def _write_pyproject(path: str, body: str) -> None:
    """Write *body* as pyproject.toml in *path*, dedented."""
    with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(body))


class TestGetCheckTimeout:
    """Tests for the get_check_timeout function."""

    def test_no_pyproject_uses_builtin_default(self, tmp_path: object) -> None:
        """No pyproject.toml and no CLI value falls back to 120."""
        assert get_check_timeout(str(tmp_path), "mypy") == DEFAULT_CHECK_TIMEOUT

    def test_no_pyproject_pytest_uses_pytest_default(self, tmp_path: object) -> None:
        """pytest has its own built-in default of 300."""
        assert get_check_timeout(str(tmp_path), "pytest") == DEFAULT_PYTEST_TIMEOUT

    def test_cli_timeout_beats_builtin(self, tmp_path: object) -> None:
        """A CLI value is used when no config key is present."""
        assert get_check_timeout(str(tmp_path), "mypy", cli_timeout=45) == 45

    def test_cli_timeout_beats_pytest_builtin(self, tmp_path: object) -> None:
        """The CLI value also overrides pytest's higher built-in."""
        assert get_check_timeout(str(tmp_path), "pytest", cli_timeout=45) == 45

    def test_shared_key_beats_cli_timeout(self, tmp_path: object) -> None:
        """check-timeout in pyproject.toml outranks --check-timeout."""
        path = str(tmp_path)
        _write_pyproject(
            path,
            """\
            [tool.mcp-tools-py]
            check-timeout = 200
            """,
        )
        assert get_check_timeout(path, "mypy", cli_timeout=45) == 200

    def test_per_tool_key_beats_shared_key(self, tmp_path: object) -> None:
        """mypy-timeout applies to mypy only; pylint gets check-timeout."""
        path = str(tmp_path)
        _write_pyproject(
            path,
            """\
            [tool.mcp-tools-py]
            check-timeout = 200
            mypy-timeout = 600
            """,
        )
        assert get_check_timeout(path, "mypy") == 600
        assert get_check_timeout(path, "pylint") == 200

    def test_explicit_beats_every_configured_value(self, tmp_path: object) -> None:
        """An explicit per-call value wins over config and CLI."""
        path = str(tmp_path)
        _write_pyproject(
            path,
            """\
            [tool.mcp-tools-py]
            check-timeout = 200
            mypy-timeout = 600
            """,
        )
        assert get_check_timeout(path, "mypy", explicit=90, cli_timeout=45) == 90

    def test_hyphenated_tool_name_resolves(self, tmp_path: object) -> None:
        """lint-imports-timeout is found for tool name 'lint-imports'."""
        path = str(tmp_path)
        _write_pyproject(
            path,
            """\
            [tool.mcp-tools-py]
            lint-imports-timeout = 30
            """,
        )
        assert get_check_timeout(path, "lint-imports") == 30

    def test_unknown_key_ignored(self, tmp_path: object) -> None:
        """An unrecognised key in the section does not affect resolution."""
        path = str(tmp_path)
        _write_pyproject(
            path,
            """\
            [tool.mcp-tools-py]
            nonsense = 1
            """,
        )
        assert get_check_timeout(path, "mypy") == DEFAULT_CHECK_TIMEOUT

    def test_section_not_a_table_treated_as_absent(self, tmp_path: object) -> None:
        """A non-table [tool] value for the section falls back to defaults."""
        path = str(tmp_path)
        _write_pyproject(
            path,
            """\
            [tool]
            mcp-tools-py = "nope"
            """,
        )
        assert get_check_timeout(path, "mypy") == DEFAULT_CHECK_TIMEOUT

    @pytest.mark.parametrize("value", [0, -1])
    def test_invalid_explicit_raises(self, tmp_path: object, value: int) -> None:
        """An invalid explicit value raises ValueError mentioning it."""
        with pytest.raises(ValueError, match="timeout_seconds"):
            get_check_timeout(str(tmp_path), "mypy", explicit=value)

    def test_invalid_cli_timeout_raises(self, tmp_path: object) -> None:
        """An invalid CLI value raises ValueError naming --check-timeout."""
        with pytest.raises(ValueError, match="--check-timeout"):
            get_check_timeout(str(tmp_path), "mypy", cli_timeout=0)

    @pytest.mark.parametrize("value", ["0", "-5", '"600"', "true"])
    def test_invalid_configured_value_raises(
        self, tmp_path: object, value: str
    ) -> None:
        """An invalid value under a known key raises ValueError naming the key."""
        path = str(tmp_path)
        _write_pyproject(
            path,
            f"""\
            [tool.mcp-tools-py]
            mypy-timeout = {value}
            """,
        )
        with pytest.raises(ValueError, match="mypy-timeout"):
            get_check_timeout(path, "mypy")

    def test_malformed_pyproject_raises(self, tmp_path: object) -> None:
        """Invalid TOML raises ValueError, not TOMLDecodeError."""
        path = str(tmp_path)
        with open(os.path.join(path, "pyproject.toml"), "w", encoding="utf-8") as f:
            f.write("invalid toml {{{{")

        with pytest.raises(ValueError, match="Invalid pyproject.toml"):
            get_check_timeout(path, "mypy")
