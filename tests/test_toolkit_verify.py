"""Tests for PythonToolkit.verify()."""

from pathlib import Path

import pytest

from mcp_tools_py.toolkit import PythonToolkit
from mcp_tools_py.utils.tool_context import ToolContext

_RUFF_PYPROJECT = '[tool.ruff.format]\nquote-style = "double"\n'


class TestVerify:
    """verify() checks every tool PythonToolkit drives, plus the formatter."""

    def test_healthy_environment_is_all_ok(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(_RUFF_PYPROJECT)

        items = PythonToolkit().verify(tmp_path)

        assert len(items) == 12
        assert all(item.status == "ok" for item in items)
        names = {item.name for item in items}
        assert names == {
            "mypy",
            "pylint",
            "pytest",
            "deptry",
            "black",
            "isort",
            "ruff",
            "bandit",
            "vulture",
            "tach",
            "lint-imports",
            "formatter",
        }

    def test_missing_console_script_tool_is_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(_RUFF_PYPROJECT)
        monkeypatch.setattr(
            ToolContext,
            "is_tool_available",
            lambda self, tool_name: tool_name != "bandit",
        )

        items = PythonToolkit().verify(tmp_path)

        by_name = {item.name: item for item in items}
        assert by_name["bandit"].status == "error"
        assert by_name["bandit"].message
        assert by_name["mypy"].status == "ok"
        assert by_name["formatter"].status == "ok"

    def test_no_formatter_declared_is_error(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')

        items = PythonToolkit().verify(tmp_path)

        by_name = {item.name: item for item in items}
        assert by_name["formatter"].status == "error"
        assert by_name["formatter"].message

    def test_stale_virtual_env_is_single_environment_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "missing"))

        items = PythonToolkit().verify(tmp_path)

        assert len(items) == 1
        assert items[0].name == "environment"
        assert items[0].status == "error"
        assert "VIRTUAL_ENV" in items[0].message


class TestVerifyAction:
    """verify(action=...) checks only the tools that action drives."""

    def test_format_on_ruff_project_reports_formatter_and_ruff(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(_RUFF_PYPROJECT)

        items = PythonToolkit().verify(tmp_path, "format")

        assert {item.name for item in items} == {"formatter", "ruff"}
        assert all(item.status == "ok" for item in items)

    def test_format_on_black_project_reports_black_and_isort(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("[tool.black]\nline-length = 88\n")

        items = PythonToolkit().verify(tmp_path, "format")

        assert {item.name for item in items} == {"formatter", "black", "isort"}

    def test_format_without_formatter_is_formatter_error_only(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')

        items = PythonToolkit().verify(tmp_path, "format")

        assert len(items) == 1
        assert items[0].name == "formatter"
        assert items[0].status == "error"
        assert items[0].message

    def test_check_reports_every_full_tool(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(_RUFF_PYPROJECT)

        items = PythonToolkit().verify(tmp_path, "check")

        assert {item.name for item in items} == {
            "mypy",
            "pylint",
            "vulture",
            "lint-imports",
            "tach",
            "ruff",
            "bandit",
            "deptry",
        }

    def test_test_reports_pytest(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(_RUFF_PYPROJECT)

        items = PythonToolkit().verify(tmp_path, "test")

        assert {item.name for item in items} == {"pytest"}

    def test_undeclared_action_is_error(self, tmp_path: Path) -> None:
        items = PythonToolkit().verify(tmp_path, "deploy")

        assert len(items) == 1
        assert items[0].name == "deploy"
        assert items[0].status == "error"
        assert items[0].message
