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

        assert len(items) == 11
        assert all(item.status == "ok" for item in items)
        names = {item.name for item in items}
        assert names == {
            "mypy",
            "pylint",
            "pytest",
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
