"""The workers note of `check_code_with_pytest` in the toolkit `test` action."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from mcp_coder_utils.toolkit import ActionRequest, ActionResult

from mcp_tools_py.code_checker_pytest.models import ErrorContext, PytestReport, Summary
from mcp_tools_py.code_checker_pytest.pytest_config import EffectiveConfig
from mcp_tools_py.code_checker_pytest.verdict import RunStatus, RunVerdict
from mcp_tools_py.toolkit import PythonToolkit
from tests._pytest_results import make_pytest_results

_NOTE = "workers: 4 (config.toml)"


def _report(collected: int, passed: int | None = None) -> PytestReport:
    return PytestReport(
        created=0.0,
        duration=0.0,
        exitcode=0,
        root="",
        environment={},
        summary=Summary(collected=collected, total=collected, passed=passed),
    )


def _passed_results(**extra: Any) -> dict[str, Any]:
    results = make_pytest_results(
        RunStatus.PASSED,
        test_results=_report(1, passed=1),
        summary_text="Collected 1 tests in 0.0 seconds",
    )
    return {**results, **extra}


def _error_results(problems: list[str], exit_code: int) -> dict[str, Any]:
    report = _report(0)
    report.error_context = ErrorContext(
        exit_code=exit_code,
        exit_code_meaning="",
        error_message="INTERNALERROR> boom",
        suggestion="",
    )
    return {
        "verdict": RunVerdict(RunStatus.ERROR, problems, exit_code),
        "summary_text": "Collected 0 tests in 0.0 seconds",
        "test_results": report,
        "workers_note": _NOTE,
    }


def _run_with(tmp_path: Path, results: dict[str, Any]) -> ActionResult:
    request = ActionRequest(
        action="test", depth="standard", project_dir=tmp_path, params={}
    )
    with patch("mcp_tools_py.toolkit.check_code_with_pytest", return_value=results):
        return PythonToolkit().run(request)


class TestWorkersNote:
    """The workers note leads the summary, ahead of the test paths note."""

    def test_passed_summary_starts_with_workers_note(self, tmp_path: Path) -> None:
        result = _run_with(tmp_path, _passed_results(workers_note=_NOTE))

        assert result.status == "ok"
        assert result.summary.startswith(f"{_NOTE}\n\n")

    def test_workers_note_precedes_test_paths_note(self, tmp_path: Path) -> None:
        results = _passed_results(workers_note=_NOTE, test_paths_note="PATHS NOTE")

        result = _run_with(tmp_path, results)

        assert result.summary.startswith(f"{_NOTE}\nPATHS NOTE\n\n")

    def test_no_workers_note_leaves_summary_unchanged(self, tmp_path: Path) -> None:
        result = _run_with(tmp_path, _passed_results(workers_note=None))

        assert result.summary == "Collected 1 tests in 0.0 seconds"

    def test_error_carries_workers_note(self, tmp_path: Path) -> None:
        result = _run_with(tmp_path, _error_results(["problem"], 3))

        assert result.status == "error"
        assert result.summary.startswith(f"{_NOTE}\n\n")

    def test_skipped_carries_workers_note(self, tmp_path: Path) -> None:
        result = _run_with(tmp_path, _error_results(["No Tests Found: none"], 5))

        assert result.status == "skipped"
        assert result.summary.startswith(f"{_NOTE}\n\n")


def _write_coverage_project(project_dir: Path) -> None:
    (project_dir / "src" / "pkg").mkdir(parents=True)
    (project_dir / "src" / "pkg" / "__init__.py").write_text("")
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_mod.py").write_text("def test_ok():\n    pass\n")
    (project_dir / "pyproject.toml").write_text(
        "[tool.setuptools.packages.find]\n"
        'where = ["src"]\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
        'pythonpath = ["src"]\n'
    )


class TestEffectivePassed:
    """`full` passes its parsed config on; other depths let the runner parse."""

    def test_full_passes_effective(self, tmp_path: Path) -> None:
        pytest.importorskip("pytest_cov")
        _write_coverage_project(tmp_path)
        request = ActionRequest(
            action="test", depth="full", project_dir=tmp_path, params={}
        )

        with (
            patch(
                "mcp_tools_py.toolkit.check_code_with_pytest",
                return_value=_passed_results(),
            ) as mock_pytest,
            patch("mcp_tools_py.toolkit.finish_coverage_run", return_value=None),
        ):
            PythonToolkit().run(request)

        assert isinstance(mock_pytest.call_args.kwargs["effective"], EffectiveConfig)

    @pytest.mark.parametrize("depth", ["quick", "standard"])
    def test_other_depths_pass_none(self, tmp_path: Path, depth: str) -> None:
        request = ActionRequest(
            action="test", depth=depth, project_dir=tmp_path, params={}
        )

        with (
            patch("mcp_tools_py.toolkit._registered_markers", return_value=[]),
            patch(
                "mcp_tools_py.toolkit.check_code_with_pytest",
                return_value=_passed_results(),
            ) as mock_pytest,
        ):
            PythonToolkit().run(request)

        assert mock_pytest.call_args.kwargs["effective"] is None
