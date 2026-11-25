"""Integration tests for runners.py marker filtering and runner behaviour."""

import json
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.code_checker_pytest.models import Collector, PytestReport, Summary
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
from mcp_tools_py.code_checker_pytest.runners import (
    _SKIP_REPORT_ATTR,
    check_code_with_pytest,
    marker_error_line,
    run_tests,
)
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from mcp_tools_py.server import ToolServer
from mcp_tools_py.utils.subprocess_runner import MAX_STDERR_IN_ERROR
from tests._pytest_results import make_pytest_results
from tests.conftest import make_command_result
from tests.test_code_checker_pytest._helpers import _create_large_project

_EXECUTE = "mcp_tools_py.code_checker_pytest.runners.execute_command"
_REPORT_ARG = "--json-report-file="

_UNKNOWN_MARKER = (
    "ERROR: Unknown marker(s) in '-m' expression: unit. "
    "Use 'pytest --markers' to see available markers."
)
_WRONG_EXPRESSION = (
    "ERROR: Wrong expression passed to '-m': unit and: "
    "at column 9: expected not OR left parenthesis OR identifier; got end of input"
)


def _check(project: Path) -> dict[str, Any]:
    """Run check_code_with_pytest on a project with a tests folder."""
    (project / "tests").mkdir(exist_ok=True)
    return check_code_with_pytest(str(project), python_executable=sys.executable)


class TestMarkerErrorLine:
    """Unit tests for marker_error_line."""

    def test_unknown_marker_line(self) -> None:
        """The Unknown-marker ERROR: line is returned, stripped."""
        stderr = f"some warning\n  {_UNKNOWN_MARKER}  \n"
        assert marker_error_line(stderr) == _UNKNOWN_MARKER

    def test_wrong_expression_line(self) -> None:
        """The Wrong-expression ERROR: line is returned."""
        assert marker_error_line(_WRONG_EXPRESSION) == _WRONG_EXPRESSION

    def test_no_error_line(self) -> None:
        """No ERROR: line gives None."""
        assert marker_error_line("warning: something\nmore text") is None

    def test_error_line_not_about_m(self) -> None:
        """An ERROR: line about something else gives None."""
        assert marker_error_line("ERROR: unrecognized arguments: --bogus") is None

    def test_marker_text_without_error_prefix(self) -> None:
        """The marker message outside an ERROR: line gives None."""
        assert marker_error_line("note: Unknown marker(s) in '-m' expression") is None


class TestExitCodeTransport:
    """check_code_with_pytest returns exit_code and marker_error on both paths."""

    @patch(_EXECUTE)
    def test_unknown_marker_after_long_stderr(
        self, mock_exec: MagicMock, tmp_path: Path
    ) -> None:
        """The ERROR: line comes from the full stderr; problems keep the cut."""
        warnings = "W" * 600
        mock_exec.return_value = make_command_result(
            return_code=4, stderr=f"{warnings}\n{_UNKNOWN_MARKER}\n"
        )

        result = _check(tmp_path)

        assert result["exit_code"] == 4
        assert result["marker_error"] == _UNKNOWN_MARKER
        verdict = result["verdict"]
        assert verdict.status is RunStatus.ERROR
        assert verdict.exit_code == 0
        assert verdict.problems[0].startswith("Usage Error:")
        assert f"stderr: {'W' * MAX_STDERR_IN_ERROR}..." in verdict.problems[0]
        assert "Unknown marker" not in verdict.problems[0]
        assert not any("Unknown marker" in p for p in verdict.problems)

    @patch(_EXECUTE)
    def test_wrong_expression(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        """A Wrong-expression error on exit 4 sets marker_error."""
        mock_exec.return_value = make_command_result(
            return_code=4, stderr=f"{_WRONG_EXPRESSION}\n"
        )

        result = _check(tmp_path)

        assert result["exit_code"] == 4
        assert result["marker_error"] == _WRONG_EXPRESSION

    @patch(_EXECUTE)
    def test_unrelated_usage_error(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        """A usage error not about -m leaves marker_error None."""
        mock_exec.return_value = make_command_result(
            return_code=4, stderr="ERROR: unrecognized arguments: --bogus\n"
        )

        result = _check(tmp_path)

        assert result["exit_code"] == 4
        assert result["marker_error"] is None

    @patch(_EXECUTE)
    def test_marker_line_ignored_off_exit_4(
        self, mock_exec: MagicMock, tmp_path: Path
    ) -> None:
        """The -m ERROR: line is only read on exit 4."""
        mock_exec.return_value = make_command_result(
            return_code=3, stderr=f"{_UNKNOWN_MARKER}\n"
        )

        result = _check(tmp_path)

        assert result["exit_code"] == 3
        assert result["marker_error"] is None

    @patch(_EXECUTE)
    def test_no_tests_found(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        """Exit 5 is transported; problems still start with No Tests Found."""
        mock_exec.return_value = make_command_result(
            return_code=5, stdout="collected 0 items"
        )

        result = _check(tmp_path)

        assert result["exit_code"] == 5
        assert result["marker_error"] is None
        assert result["verdict"].problems[0].startswith("No Tests Found")
        assert result["verdict"].exit_code == 0

    @patch(_EXECUTE)
    def test_no_tests_found_without_report_file(
        self, mock_exec: MagicMock, tmp_path: Path
    ) -> None:
        """Exit 5 without a report file leaves skip_report None."""
        mock_exec.return_value = make_command_result(return_code=5)

        result = _check(tmp_path)

        assert result["skip_report"] is None

    @patch("mcp_tools_py.code_checker_pytest.runners.run_tests")
    def test_skip_report_from_attribute(
        self, mock_run_tests: MagicMock, tmp_path: Path
    ) -> None:
        """check_code_with_pytest returns the report attached to the exception."""
        report = _exit5_report(tmp_path)
        error = ValueError("No Tests Found: Pytest did not find any tests to run.")
        setattr(error, _SKIP_REPORT_ATTR, report)
        mock_run_tests.side_effect = error

        result = _check(tmp_path)

        assert result["skip_report"] is report
        assert result["verdict"].status is RunStatus.ERROR

    @patch(_EXECUTE)
    def test_internal_error(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        """Exit 3 is transported."""
        mock_exec.return_value = make_command_result(
            return_code=3, stdout="INTERNALERROR> boom"
        )

        result = _check(tmp_path)

        assert result["exit_code"] == 3
        assert result["verdict"].exit_code == 0

    @patch(_EXECUTE)
    def test_timeout(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        """A timeout has no exit code."""
        mock_exec.return_value = make_command_result(
            return_code=1, timed_out=True, execution_error="timed out"
        )

        result = _check(tmp_path)

        assert result["exit_code"] is None
        assert result["marker_error"] is None
        assert result["verdict"].status is RunStatus.ERROR

    @patch(_EXECUTE)
    def test_execution_error(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        """An execution error has no exit code."""
        mock_exec.return_value = make_command_result(
            return_code=1, execution_error="FileNotFoundError: python"
        )

        result = _check(tmp_path)

        assert result["exit_code"] is None
        assert result["marker_error"] is None

    @patch("mcp_tools_py.code_checker_pytest.runners.run_tests")
    def test_success_path(self, mock_run_tests: MagicMock, tmp_path: Path) -> None:
        """On success, exit_code is the verdict's and marker_error is None."""
        mock_run_tests.return_value = PytestReport(
            created=0.0,
            duration=0.1,
            exitcode=0,
            root=str(tmp_path),
            environment={},
            summary=Summary(collected=1, total=1, passed=1),
        )

        result = _check(tmp_path)

        assert result["verdict"].status is RunStatus.PASSED
        assert result["exit_code"] == result["verdict"].exit_code
        assert result["marker_error"] is None
        assert result["skip_report"] is None


def _exit5_report(root: Path) -> PytestReport:
    """A report with one module-skipped collector and no tests."""
    longrepr = str((str(root / "tests" / "test_a.py"), 3, "Skipped: no db"))
    return PytestReport(
        created=0.0,
        duration=0.1,
        exitcode=5,
        root=str(root),
        environment={},
        summary=Summary(collected=0, total=0),
        collectors=[
            Collector(
                nodeid="tests/test_a.py",
                outcome="skipped",
                result=[],
                longrepr=longrepr,
            )
        ],
    )


def _write_report(content: str | None) -> Any:
    """An execute_command side effect: write `content` to the report file, exit 5."""

    def run(command: list[str], **_kwargs: Any) -> Any:
        if content is not None:
            for arg in command:
                if arg.startswith(_REPORT_ARG):
                    Path(arg[len(_REPORT_ARG) :]).write_text(content, encoding="utf-8")
        return make_command_result(return_code=5, stdout="collected 0 items")

    return run


def _call_run_tests(project: Path) -> ValueError:
    """Run run_tests on `project`, expecting the exit-5 ValueError."""
    (project / "tests").mkdir(exist_ok=True)
    with pytest.raises(ValueError) as info:
        run_tests(str(project), None, sys.executable)
    return info.value


class TestExit5Report:
    """run_tests attaches the parsed report to the exit-5 ValueError."""

    @patch(_EXECUTE)
    def test_report_attached(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        """A written report is parsed and attached; the message is unchanged."""
        data = {
            "created": 0.0,
            "duration": 0.1,
            "exitcode": 5,
            "root": str(tmp_path),
            "environment": {},
            "summary": {"collected": 0, "total": 0},
            "collectors": [
                {
                    "nodeid": "tests/test_a.py",
                    "outcome": "skipped",
                    "result": [],
                    "longrepr": "('tests/test_a.py', 3, 'Skipped: no db')",
                }
            ],
        }
        mock_exec.side_effect = _write_report(json.dumps(data))

        error = _call_run_tests(tmp_path)

        report = getattr(error, _SKIP_REPORT_ATTR)
        assert isinstance(report, PytestReport)
        assert report.collectors is not None
        assert report.collectors[0].outcome == "skipped"
        assert str(error).startswith(
            "No Tests Found: Pytest did not find any tests to run."
        )

    @patch(_EXECUTE)
    def test_no_report_file(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        """Without a report file the attribute is None."""
        mock_exec.side_effect = _write_report(None)

        error = _call_run_tests(tmp_path)

        assert getattr(error, _SKIP_REPORT_ATTR) is None
        assert str(error).startswith("No Tests Found")

    @patch(_EXECUTE)
    def test_invalid_json(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        """An unreadable report file gives None; the message is unchanged."""
        mock_exec.side_effect = _write_report("{not json")

        error = _call_run_tests(tmp_path)

        assert getattr(error, _SKIP_REPORT_ATTR) is None
        assert str(error).startswith("No Tests Found")

    @patch(_EXECUTE)
    def test_incomplete_json(self, mock_exec: MagicMock, tmp_path: Path) -> None:
        """Valid JSON missing report keys gives None."""
        mock_exec.side_effect = _write_report(json.dumps({"summary": {}}))

        error = _call_run_tests(tmp_path)

        assert getattr(error, _SKIP_REPORT_ATTR) is None


class TestRunners:
    """Integration tests for runners.py end-to-end flow."""

    def test_marker_filtering_with_details(self, temp_project_dir: Path) -> None:
        """Test marker filtering combined with show_details."""
        (temp_project_dir / "tests").mkdir(parents=True, exist_ok=True)

        # Create test with markers
        (temp_project_dir / "tests" / "test_markers.py").write_text("""
import pytest

@pytest.mark.slow
def test_slow_operation():
    print("Debug: slow operation starting")
    assert 1 == 2  # Intentional failure

@pytest.mark.fast  
def test_fast_operation():
    print("Debug: fast operation")
    assert True
""")

        server = ToolServer(project_dir=temp_project_dir)

        # Create proper PytestReport structure
        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.1235666275024414,
            "exitcode": 1,
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {"collected": 1, "passed": 0, "failed": 1, "total": 1},
            "collectors": [],
            "tests": [
                {
                    "nodeid": "tests/test_markers.py::test_slow_operation",
                    "lineno": 10,
                    "keywords": ["test_slow_operation", "slow"],
                    "outcome": "failed",
                    "call": {
                        "duration": 0.001,
                        "outcome": "failed",
                        "longrepr": "AssertionError: assert 1 == 2",
                        "stdout": "Debug: slow operation starting\n",
                        "stderr": "",
                        "crash": {
                            "path": str(temp_project_dir / "tests" / "test_markers.py"),
                            "lineno": 6,
                            "message": "AssertionError: assert 1 == 2",
                        },
                    },
                }
            ],
            "warnings": [],
        }

        pytest_report = parse_pytest_report(json.dumps(json_report))

        test_results = make_pytest_results(
            RunStatus.FAILED,
            summary=json_report["summary"],
            test_results=pytest_report,
        )

        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )

        # Should include debug output from the marked test
        assert "Debug: slow operation starting" in result

    def test_performance_validation(self, temp_project_dir: Path) -> None:
        """Test that integration has reasonable performance."""
        _create_large_project(temp_project_dir)
        server = ToolServer(project_dir=temp_project_dir)

        # Create proper PytestReport structure for performance test
        test_entries = []
        for i in range(7):
            test_entries.append(
                {
                    "nodeid": f"tests/test_module_b.py::test_b{i}_fail",
                    "lineno": 10,
                    "keywords": [f"test_b{i}_fail"],
                    "outcome": "failed",
                    "call": {
                        "duration": 0.001,
                        "outcome": "failed",
                        "longrepr": f"AssertionError: Test {i} failed",
                        "stdout": f"Debug: test {i} output\n",
                        "stderr": "",
                        "crash": {
                            "path": str(
                                temp_project_dir / "tests" / "test_module_b.py"
                            ),
                            "lineno": 15,
                            "message": f"AssertionError: Test {i} failed",
                        },
                    },
                }
            )

        json_report = {
            "created": 1518371686.7981803,
            "duration": 0.5,
            "exitcode": 1,
            "root": str(temp_project_dir),
            "environment": {},
            "summary": {"collected": 23, "passed": 16, "failed": 7, "total": 23},
            "collectors": [],
            "tests": test_entries,
            "warnings": [],
        }

        pytest_report = parse_pytest_report(json.dumps(json_report))

        test_results = make_pytest_results(
            RunStatus.FAILED,
            summary=json_report["summary"],
            test_results=pytest_report,
        )

        start_time = time.time()
        result = CheckerTools(server.context)._format_pytest_result_with_details(
            test_results, show_details=True
        )
        end_time = time.time()

        # Should complete within reasonable time (< 1 second for formatting)
        assert end_time - start_time < 1.0
        assert len(result) > 0  # Should produce output
