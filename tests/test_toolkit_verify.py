"""Tests for PythonToolkit.verify()."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp_coder_utils.toolkit import VerifyItem

from mcp_tools_py.toolkit import PythonToolkit
from mcp_tools_py.utils.environment_info import EnvironmentInfo
from mcp_tools_py.utils.tool_context import ToolContext
from tests.conftest import make_environment_info

_RUFF_PYPROJECT = '[tool.ruff.format]\nquote-style = "double"\n'
_GET_ENVIRONMENT_INFO = "mcp_tools_py.utils.tool_context.get_environment_info"
_BOTH = make_environment_info(
    distributions={"pytest-json-report": "1.5.0", "pytest-cov": "7.1.0"}
)


class TestVerify:
    """verify() checks every tool PythonToolkit drives, plus the formatter."""

    def test_healthy_environment_is_all_ok(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(_RUFF_PYPROJECT)

        with patch(_GET_ENVIRONMENT_INFO, return_value=_BOTH):
            items = PythonToolkit().verify(tmp_path)

        assert len(items) == 15
        assert all(item.status == "ok" for item in items)
        names = {item.name for item in items}
        assert names == {
            "pytest_workers",
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
            "pytest-json-report",
            "pytest-cov",
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

        with patch(_GET_ENVIRONMENT_INFO, return_value=_BOTH):
            items = PythonToolkit().verify(tmp_path, "test")

        assert {item.name for item in items} == {
            "pytest",
            "pytest-json-report",
            "pytest-cov",
            "pytest_workers",
        }

    @pytest.mark.parametrize("action", ["format", "check"])
    def test_non_test_actions_omit_pytest_workers(
        self, tmp_path: Path, action: str
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(_RUFF_PYPROJECT)

        items = PythonToolkit().verify(tmp_path, action)

        assert "pytest_workers" not in {item.name for item in items}

    @pytest.mark.parametrize("action", [None, "test"])
    def test_missing_plugins_are_error_and_warning(
        self, tmp_path: Path, action: str | None
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(_RUFF_PYPROJECT)

        with patch(
            _GET_ENVIRONMENT_INFO,
            return_value=make_environment_info(distributions={}),
        ):
            items = PythonToolkit().verify(tmp_path, action)

        by_name = {item.name: item for item in items}
        assert by_name["pytest-json-report"].status == "error"
        assert (
            "pytest-json-report is not available"
            in by_name["pytest-json-report"].message
        )
        assert by_name["pytest-cov"].status == "warning"
        assert "full" in by_name["pytest-cov"].message

    @pytest.mark.parametrize("action", [None, "test"])
    def test_broken_probe_fails_open(self, tmp_path: Path, action: str | None) -> None:
        (tmp_path / "pyproject.toml").write_text(_RUFF_PYPROJECT)
        broken = EnvironmentInfo(
            version="", sys_path=(), distributions={}, importable={}, error="boom"
        )

        with patch(_GET_ENVIRONMENT_INFO, return_value=broken):
            items = PythonToolkit().verify(tmp_path, action)

        by_name = {item.name: item for item in items}
        assert by_name["pytest-json-report"].status == "ok"
        assert by_name["pytest-cov"].status == "ok"

    def test_undeclared_action_is_error(self, tmp_path: Path) -> None:
        items = PythonToolkit().verify(tmp_path, "deploy")

        assert len(items) == 1
        assert items[0].name == "deploy"
        assert items[0].status == "error"
        assert items[0].message


class TestVerifyPytestWorkers:
    """verify() reports the pytest_workers setting for actions None and "test"."""

    @staticmethod
    def _item(tmp_path: Path, action: str | None) -> VerifyItem:
        (tmp_path / "pyproject.toml").write_text(_RUFF_PYPROJECT)
        with patch(_GET_ENVIRONMENT_INFO, return_value=_BOTH):
            items = PythonToolkit().verify(tmp_path, action)
        by_name = {item.name: item for item in items}
        return by_name["pytest_workers"]

    @pytest.mark.parametrize("action", [None, "test"])
    def test_no_config_is_auto_default(
        self, tmp_path: Path, action: str | None
    ) -> None:
        item = self._item(tmp_path, action)

        assert item.status == "ok"
        assert item.message == "auto (default)"
        assert item.hint is None

    @pytest.mark.parametrize("action", [None, "test"])
    def test_integer_from_config(
        self,
        tmp_path: Path,
        action: str | None,
        user_config: Callable[[str], Path],
    ) -> None:
        user_config("[mcp_tools_py]\npytest_workers = 4\n")

        item = self._item(tmp_path, action)

        assert item.status == "ok"
        assert item.message == "4 (config.toml)"

    @pytest.mark.parametrize("action", [None, "test"])
    def test_invalid_value_is_warning_with_valid_values(
        self,
        tmp_path: Path,
        action: str | None,
        user_config: Callable[[str], Path],
    ) -> None:
        user_config('[mcp_tools_py]\npytest_workers = "x"\n')

        item = self._item(tmp_path, action)

        assert item.status == "warning"
        assert item.hint is not None
        assert '"auto"' in item.hint
        assert '"all"' in item.hint
        assert "integer" in item.hint

    @pytest.mark.parametrize("action", [None, "test"])
    def test_invalid_toml_is_warning(
        self,
        tmp_path: Path,
        action: str | None,
        user_config: Callable[[str], Path],
    ) -> None:
        user_config("[mcp_tools_py\npytest_workers = 4\n")

        item = self._item(tmp_path, action)

        assert item.status == "warning"
        assert "invalid TOML" in item.message
