"""Tests for the lint-imports PYTHONPATH bridge: config, env and handover."""

import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_lint_imports.runners import (
    _pythonpath_env,
    _root_packages,
    run_lint_imports_check_impl,
)
from tests.conftest import make_command_result
from tests.test_code_checker_lint_imports._fixtures import CLEAN_OUTPUT, MODULE_PATH


class TestRootPackages:
    """_root_packages mirrors the lint-imports CLI's config discovery."""

    def test_importlinter_scalar_root_package(self, tmp_path: Path) -> None:
        (tmp_path / ".importlinter").write_text(
            "[importlinter]\nroot_package = pkg\n", encoding="utf-8"
        )
        assert _root_packages(str(tmp_path), []) == ["pkg"]

    def test_setup_cfg_wins_over_importlinter(self, tmp_path: Path) -> None:
        (tmp_path / "setup.cfg").write_text(
            "[importlinter]\nroot_package = from_setup_cfg\n", encoding="utf-8"
        )
        (tmp_path / ".importlinter").write_text(
            "[importlinter]\nroot_package = from_importlinter\n", encoding="utf-8"
        )
        assert _root_packages(str(tmp_path), []) == ["from_setup_cfg"]

    def test_pyproject_toml_root_packages_list(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.importlinter]\nroot_packages = ["a", "b"]\n', encoding="utf-8"
        )
        assert _root_packages(str(tmp_path), []) == ["a", "b"]

    def test_pyproject_toml_scalar_root_package(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.importlinter]\nroot_package = "solo"\n', encoding="utf-8"
        )
        assert _root_packages(str(tmp_path), []) == ["solo"]

    def test_ini_newline_separated_root_packages(self, tmp_path: Path) -> None:
        (tmp_path / ".importlinter").write_text(
            "[importlinter]\nroot_packages =\n    first\n    second\n", encoding="utf-8"
        )
        assert _root_packages(str(tmp_path), []) == ["first", "second"]

    def test_config_flag_separate_value_ini(self, tmp_path: Path) -> None:
        (tmp_path / ".importlinter").write_text(
            "[importlinter]\nroot_package = ignored\n", encoding="utf-8"
        )
        (tmp_path / "custom.ini").write_text(
            "[importlinter]\nroot_package = chosen\n", encoding="utf-8"
        )
        result = _root_packages(str(tmp_path), ["--config", "custom.ini"])
        assert result == ["chosen"]

    def test_config_flag_equals_value_toml(self, tmp_path: Path) -> None:
        (tmp_path / ".importlinter").write_text(
            "[importlinter]\nroot_package = ignored\n", encoding="utf-8"
        )
        (tmp_path / "custom.toml").write_text(
            '[tool.importlinter]\nroot_package = "chosen"\n', encoding="utf-8"
        )
        result = _root_packages(str(tmp_path), ["--config=custom.toml"])
        assert result == ["chosen"]

    def test_config_flag_resolved_relative_to_project_dir(self, tmp_path: Path) -> None:
        nested = tmp_path / "conf"
        nested.mkdir()
        (nested / "custom.ini").write_text(
            "[importlinter]\nroot_package = nested_pkg\n", encoding="utf-8"
        )
        result = _root_packages(str(tmp_path), ["--config", "conf/custom.ini"])
        assert result == ["nested_pkg"]

    def test_config_flag_missing_file_returns_empty(self, tmp_path: Path) -> None:
        result = _root_packages(str(tmp_path), ["--config", "nope.ini"])
        assert result == []

    def test_no_config_file_returns_empty(self, tmp_path: Path) -> None:
        assert _root_packages(str(tmp_path), []) == []

    def test_no_importlinter_section_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "setup.cfg").write_text(
            "[metadata]\nname = something\n", encoding="utf-8"
        )
        (tmp_path / "pyproject.toml").write_text(
            "[tool.black]\nline-length = 88\n", encoding="utf-8"
        )
        assert _root_packages(str(tmp_path), []) == []

    def test_malformed_toml_returns_empty(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.importlinter\nroot_package = broken", encoding="utf-8"
        )
        assert _root_packages(str(tmp_path), []) == []

    def test_discovery_stops_at_section_naming_nothing(self, tmp_path: Path) -> None:
        """setup.cfg with an empty section wins; .importlinter is never read."""
        (tmp_path / "setup.cfg").write_text("[importlinter]\n", encoding="utf-8")
        (tmp_path / ".importlinter").write_text(
            "[importlinter]\nroot_package = pkg\n", encoding="utf-8"
        )
        assert _root_packages(str(tmp_path), []) == []

    def test_section_without_root_package_skips_to_next_file(
        self, tmp_path: Path
    ) -> None:
        """pyproject.toml without the section falls through to .importlinter."""
        (tmp_path / "pyproject.toml").write_text(
            "[tool.black]\nline-length = 88\n", encoding="utf-8"
        )
        (tmp_path / ".importlinter").write_text(
            "[importlinter]\nroot_package = pkg\n", encoding="utf-8"
        )
        assert _root_packages(str(tmp_path), []) == ["pkg"]


class TestPythonpathEnv:
    """_pythonpath_env prepends directories to any existing PYTHONPATH."""

    def test_single_directory_without_existing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PYTHONPATH", raising=False)
        assert _pythonpath_env(["/src"]) == {"PYTHONPATH": "/src"}

    def test_two_directories_joined_in_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PYTHONPATH", raising=False)
        result = _pythonpath_env(["/first", "/second"])
        assert result == {"PYTHONPATH": os.pathsep.join(["/first", "/second"])}

    def test_existing_pythonpath_appended_last(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PYTHONPATH", "/already/there")
        result = _pythonpath_env(["/src"])
        assert result == {"PYTHONPATH": os.pathsep.join(["/src", "/already/there"])}

    def test_empty_existing_pythonpath_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PYTHONPATH", "")
        assert _pythonpath_env(["/src"]) == {"PYTHONPATH": "/src"}


class TestPythonpathBridge:
    """The located root package reaches the subprocess on PYTHONPATH."""

    @staticmethod
    def _project(tmp_path: Path) -> str:
        """Write a config naming one root package.

        Returns:
            The project directory, as `run_lint_imports_check_impl` takes it.
        """
        (tmp_path / ".importlinter").write_text(
            "[importlinter]\nroot_package = pkg\n", encoding="utf-8"
        )
        return str(tmp_path)

    @patch(f"{MODULE_PATH}.execute_command")
    @patch(f"{MODULE_PATH}.locate_packages")
    def test_usable_directory_is_prepended(
        self,
        mock_locate: Any,
        mock_exec: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A source tree goes on PYTHONPATH, asked of the project interpreter."""
        monkeypatch.delenv("PYTHONPATH", raising=False)
        mock_locate.return_value = (["/repo/src"], [])
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)

        run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir=self._project(tmp_path),
            python_executable="/project/venv/bin/python",
        )

        assert mock_exec.call_args.kwargs["env"] == {"PYTHONPATH": "/repo/src"}
        assert mock_locate.call_args[0] == ("/project/venv/bin/python", ["pkg"])

    @patch(f"{MODULE_PATH}.execute_command")
    @patch(f"{MODULE_PATH}.locate_packages")
    def test_existing_pythonpath_is_appended(
        self,
        mock_locate: Any,
        mock_exec: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An inherited PYTHONPATH keeps its entries, behind the located one."""
        monkeypatch.setenv("PYTHONPATH", "/already/there")
        mock_locate.return_value = (["/repo/src"], [])
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)

        run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir=self._project(tmp_path),
            python_executable=sys.executable,
        )

        assert mock_exec.call_args.kwargs["env"] == {
            "PYTHONPATH": os.pathsep.join(["/repo/src", "/already/there"])
        }

    @patch(f"{MODULE_PATH}.execute_command")
    @patch(f"{MODULE_PATH}.locate_packages")
    def test_site_packages_under_the_project_dir_is_still_skipped(
        self,
        mock_locate: Any,
        mock_exec: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The ordinary in-project venv layout: under the project, still skipped.

        `<project>/.venv/Lib/site-packages` is what a non-editable install of
        the project resolves to, and prepending it would put the whole
        environment ahead of the tool env's grimp.  A predicate asking "is it
        under --project-dir" would have prepended it.
        """
        monkeypatch.delenv("PYTHONPATH", raising=False)
        site_packages = str(tmp_path / ".venv" / "Lib" / "site-packages")
        mock_locate.return_value = ([], [site_packages])
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)

        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir=self._project(tmp_path),
            python_executable=sys.executable,
        )

        assert mock_exec.call_args.kwargs["env"] is None
        lines = result.splitlines()
        assert lines[0].startswith(
            "[Info: not added to PYTHONPATH, site-packages of the project interpreter"
        )
        assert site_packages in lines[0]
        assert lines[1] == "=== PASSED ==="

    @patch(f"{MODULE_PATH}.execute_command")
    @patch(f"{MODULE_PATH}.locate_packages")
    def test_usable_and_skipped_are_reported_separately(
        self,
        mock_locate: Any,
        mock_exec: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Only the usable directory is prepended, only the skipped one named."""
        monkeypatch.delenv("PYTHONPATH", raising=False)
        mock_locate.return_value = (["/repo/src"], ["/venv/lib/site-packages"])
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)

        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir=self._project(tmp_path),
            python_executable=sys.executable,
        )

        assert mock_exec.call_args.kwargs["env"] == {"PYTHONPATH": "/repo/src"}
        info_line = result.splitlines()[0]
        assert "/venv/lib/site-packages" in info_line
        assert "/repo/src" not in info_line

    @patch(f"{MODULE_PATH}.execute_command")
    @patch(f"{MODULE_PATH}.locate_packages")
    def test_nothing_located_is_reported(
        self,
        mock_locate: Any,
        mock_exec: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A root package the project interpreter cannot import is named.

        Running silently would let the tool env's own copy of the project
        answer for it, and a PASSED then says nothing about the working tree.
        """
        monkeypatch.delenv("PYTHONPATH", raising=False)
        mock_locate.return_value = ([], [])
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)

        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir=self._project(tmp_path),
            python_executable=sys.executable,
        )

        assert mock_exec.call_args.kwargs["env"] is None
        lines = result.splitlines()
        assert lines[0].startswith("[Info: nothing added to PYTHONPATH")
        assert "pkg" in lines[0]
        assert "an installed copy" in lines[0]
        assert lines[1] == "=== PASSED ==="

    @patch(f"{MODULE_PATH}.execute_command")
    @patch(f"{MODULE_PATH}.locate_packages")
    def test_locate_failure_reports_error_and_runs_nothing(
        self,
        mock_locate: Any,
        mock_exec: Any,
        tmp_path: Path,
    ) -> None:
        """A probe that could not be trusted stops the run before it starts."""
        mock_locate.return_value = "probe of /bad/python timed out after 30 seconds"

        result = run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir=self._project(tmp_path),
            python_executable="/bad/python",
        )

        assert result.startswith("=== ERROR:")
        assert "pkg" in result
        assert "timed out" in result
        mock_exec.assert_not_called()

    @patch(f"{MODULE_PATH}.execute_command")
    @patch(f"{MODULE_PATH}.locate_packages")
    def test_no_config_asks_nothing_and_sets_no_pythonpath(
        self,
        mock_locate: Any,
        mock_exec: Any,
        tmp_path: Path,
    ) -> None:
        """Without a config there is no root package to bridge."""
        mock_exec.return_value = make_command_result(return_code=0, stdout=CLEAN_OUTPUT)

        run_lint_imports_check_impl(
            lint_imports_binary="/usr/bin/lint-imports",
            project_dir=str(tmp_path),
            python_executable=sys.executable,
        )

        mock_locate.assert_not_called()
        assert mock_exec.call_args.kwargs["env"] is None
