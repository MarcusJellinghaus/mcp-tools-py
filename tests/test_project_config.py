"""Tests for utils.project_config module."""

import logging
import os
import textwrap

import pytest

from mcp_tools_py.utils.project_config import (
    get_target_directories,
    resolve_target_directories,
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
