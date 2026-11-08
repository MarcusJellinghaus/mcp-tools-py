"""Tests for `test@quick`'s selection of registered `*integration` markers."""

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from mcp_coder_utils.toolkit import ActionRequest, ActionResult

from mcp_tools_py.code_checker_pytest.models import PytestReport, Summary
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from mcp_tools_py.toolkit import PythonToolkit
from mcp_tools_py.utils.subprocess_runner import CommandResult
from tests._pytest_results import make_pytest_results
from tests.conftest import make_command_result

_SKIP_LINE = (
    "@pytest.mark.skip(reason=None): skip the given test function with an "
    "optional reason."
)
_XFAIL_LINE = (
    "@pytest.mark.xfail(condition, ..., *, reason=..., run=True, raises=None, "
    "strict=xfail_strict): mark the test function as an expected failure."
)


def _report() -> PytestReport:
    return PytestReport(
        created=0.0,
        duration=0.0,
        exitcode=0,
        root="",
        environment={},
        summary=Summary(collected=1, total=1, passed=1),
    )


def _passed_results() -> dict[str, Any]:
    return make_pytest_results(
        RunStatus.PASSED,
        test_results=_report(),
        summary_text="Collected 1 tests in 0.0 seconds",
    )


def _run_quick(
    tmp_path: Path, command_result: CommandResult
) -> tuple[ActionResult, MagicMock]:
    request = ActionRequest(
        action="test", depth="quick", project_dir=tmp_path, params={}
    )
    with (
        patch("mcp_tools_py.toolkit.execute_command", return_value=command_result),
        patch(
            "mcp_tools_py.toolkit.check_code_with_pytest",
            return_value=_passed_results(),
        ) as mock_pytest,
    ):
        result = PythonToolkit().run(request)
    return result, mock_pytest


def _stdout(*lines: str) -> str:
    return "\n\n".join(lines) + "\n"


class TestQuickMarkerSelection:
    """`quick` excludes every registered marker ending in `integration`."""

    def test_registered_integration_markers_are_excluded(self, tmp_path: Path) -> None:
        stdout = _stdout(
            "@pytest.mark.integration: needs external resources",
            "@pytest.mark.git_integration: desc",
            "@pytest.mark.slow: mentions @pytest.mark.llm_integration",
            _SKIP_LINE,
        )

        result, mock_pytest = _run_quick(tmp_path, make_command_result(stdout=stdout))

        assert result.status == "ok"
        assert mock_pytest.call_args.kwargs["markers"] == [
            "not integration",
            "not git_integration",
        ]

    def test_marker_with_arguments(self, tmp_path: Path) -> None:
        stdout = _stdout("@pytest.mark.llm_integration(model): runs an LLM", _SKIP_LINE)

        result, mock_pytest = _run_quick(tmp_path, make_command_result(stdout=stdout))

        assert result.status == "ok"
        assert mock_pytest.call_args.kwargs["markers"] == ["not llm_integration"]

    def test_none_registered_runs_unfiltered(self, tmp_path: Path) -> None:
        stdout = _stdout(_SKIP_LINE, _XFAIL_LINE)

        result, mock_pytest = _run_quick(tmp_path, make_command_result(stdout=stdout))

        assert result.status == "ok"
        assert mock_pytest.call_args.kwargs["markers"] is None

    def test_nonzero_exit_is_error(self, tmp_path: Path) -> None:
        command_result = make_command_result(return_code=4, stderr="ERROR: usage error")

        result, mock_pytest = _run_quick(tmp_path, command_result)

        assert result.status == "error"
        assert "usage error" in result.summary
        mock_pytest.assert_not_called()

    def test_exit_zero_without_marker_lines_is_error(self, tmp_path: Path) -> None:
        result, mock_pytest = _run_quick(
            tmp_path, make_command_result(return_code=0, stdout="garbage")
        )

        assert result.status == "error"
        mock_pytest.assert_not_called()

    def test_timeout_is_error(self, tmp_path: Path) -> None:
        result, mock_pytest = _run_quick(
            tmp_path, make_command_result(return_code=-1, timed_out=True)
        )

        assert result.status == "error"
        assert "timed out" in result.summary
        mock_pytest.assert_not_called()


class TestMarkerReadPath:
    """The marker read gets the real run's venv_bin on PATH and rootdir."""

    def test_marker_read_passes_project_dir_as_rootdir(self, tmp_path: Path) -> None:
        request = ActionRequest(
            action="test", depth="quick", project_dir=tmp_path, params={}
        )
        with (
            patch(
                "mcp_tools_py.toolkit.execute_command",
                return_value=make_command_result(stdout=_stdout(_SKIP_LINE)),
            ) as mock_execute,
            patch(
                "mcp_tools_py.toolkit.check_code_with_pytest",
                return_value=_passed_results(),
            ) as mock_pytest,
        ):
            PythonToolkit().run(request)

        project_dir = mock_pytest.call_args.args[0]
        command = mock_execute.call_args.args[0]
        rootdir_index = command.index("--rootdir")
        assert command[rootdir_index + 1] == project_dir

    def test_marker_read_prepends_venv_bin_to_path(self, tmp_path: Path) -> None:
        request = ActionRequest(
            action="test", depth="quick", project_dir=tmp_path, params={}
        )
        with (
            patch(
                "mcp_tools_py.toolkit.execute_command",
                return_value=make_command_result(stdout=_stdout(_SKIP_LINE)),
            ) as mock_execute,
            patch(
                "mcp_tools_py.toolkit.check_code_with_pytest",
                return_value=_passed_results(),
            ) as mock_pytest,
        ):
            PythonToolkit().run(request)

        venv_bin = mock_pytest.call_args.kwargs["venv_bin"]
        path = mock_execute.call_args.kwargs["env"]["PATH"]
        assert path.split(os.pathsep)[0] == venv_bin


class TestQuickMarkerRealRun:
    """A real `quick` run against a project using --strict-markers."""

    def test_strict_marker_project_with_conftest_registration(
        self, tmp_path: Path
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\naddopts = "--strict-markers"\n'
        )
        (tmp_path / "conftest.py").write_text(
            "def pytest_configure(config):\n"
            '    config.addinivalue_line("markers", "llm_integration: real LLM")\n'
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_mixed.py").write_text(
            "import pytest\n\n\n"
            "def test_ok():\n    assert True\n\n\n"
            "@pytest.mark.llm_integration\n"
            "def test_llm():\n    assert False\n"
        )
        request = ActionRequest(
            action="test", depth="quick", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "ok"
