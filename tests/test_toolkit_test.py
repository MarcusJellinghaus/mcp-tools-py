"""Tests for PythonToolkit's `test` action, at each depth."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from mcp_coder_utils.toolkit import ActionRequest, ActionResult

from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    PytestReport,
    Summary,
    Test,
)
from mcp_tools_py.code_checker_pytest.reporting import group_failed_collectors
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from mcp_tools_py.toolkit import PythonToolkit
from tests._pytest_results import make_pytest_results


def _write_passing_project(project_dir: Path) -> None:
    (project_dir / "tests").mkdir(parents=True)
    (project_dir / "tests" / "test_ok.py").write_text(
        "def test_ok():\n    assert 1 + 1 == 2\n"
    )


def _write_failing_project(project_dir: Path) -> None:
    (project_dir / "tests").mkdir(parents=True)
    (project_dir / "tests" / "test_fail.py").write_text(
        "def test_fails():\n    assert 1 == 2\n"
    )


def _write_empty_project(project_dir: Path) -> None:
    (project_dir / "tests").mkdir(parents=True)
    (project_dir / "tests" / "__init__.py").write_text("")


def _write_coverage_project(project_dir: Path) -> None:
    (project_dir / "src" / "pkg").mkdir(parents=True)
    (project_dir / "src" / "pkg" / "__init__.py").write_text("")
    (project_dir / "src" / "pkg" / "mod.py").write_text(
        "def covered(x):\n    return x + 1\n"
    )
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_mod.py").write_text(
        "from pkg.mod import covered\n\n\ndef test_covered():\n    assert covered(1) == 2\n"
    )
    (project_dir / "pyproject.toml").write_text(
        "[tool.setuptools.packages.find]\n"
        'where = ["src"]\n\n'
        "[tool.pytest.ini_options]\n"
        'testpaths = ["tests"]\n'
        'pythonpath = ["src"]\n'
    )


class TestRunTest:
    """run() for the `test` action, at each depth."""

    def test_quick_passing_project_is_ok(self, tmp_path: Path) -> None:
        _write_passing_project(tmp_path)
        request = ActionRequest(
            action="test", depth="quick", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "ok"
        assert result.findings == []

    def test_standard_failing_project_is_findings(self, tmp_path: Path) -> None:
        _write_failing_project(tmp_path)
        request = ActionRequest(
            action="test", depth="standard", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.key.endswith("test_fail.py::test_fails")
        assert finding.path is not None and finding.path.endswith("test_fail.py")
        assert result.fix_text

    def test_no_tests_collected_is_skipped(self, tmp_path: Path) -> None:
        _write_empty_project(tmp_path)
        request = ActionRequest(
            action="test", depth="quick", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "skipped"
        assert result.findings == []

    @pytest.mark.integration
    def test_every_module_failing_to_import_is_error(self, tmp_path: Path) -> None:
        (tmp_path / "tests").mkdir()
        for name in ("test_a.py", "test_b.py"):
            (tmp_path / "tests" / name).write_text(
                "import module_that_does_not_exist\n"
            )
        request = ActionRequest(
            action="test", depth="standard", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "error"

    def test_full_depth_sets_raw_coverage_digest(self, tmp_path: Path) -> None:
        pytest.importorskip("pytest_cov")
        _write_coverage_project(tmp_path)
        request = ActionRequest(
            action="test", depth="full", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "ok"
        assert result.raw
        assert "stmts" in result.raw

    def test_unknown_action_raises(self, tmp_path: Path) -> None:
        request = ActionRequest(
            action="bogus", depth="quick", project_dir=tmp_path, params={}
        )

        with pytest.raises(NotImplementedError):
            PythonToolkit().run(request)


def _report(
    collected: int,
    *,
    passed: int | None = None,
    failed: int | None = None,
    tests: list[Test] | None = None,
    collectors: list[Collector] | None = None,
) -> PytestReport:
    return PytestReport(
        created=0.0,
        duration=0.0,
        exitcode=0,
        root="",
        environment={},
        summary=Summary(
            collected=collected, total=collected, passed=passed, failed=failed
        ),
        collectors=collectors,
        tests=tests,
    )


def _run_with(tmp_path: Path, results: dict[str, Any]) -> ActionResult:
    request = ActionRequest(
        action="test", depth="standard", project_dir=tmp_path, params={}
    )
    with patch("mcp_tools_py.toolkit.check_code_with_pytest", return_value=results):
        return PythonToolkit().run(request)


class TestRunTestVerdictMapping:
    """_run_test maps each verdict status onto an ActionResult."""

    def test_error_with_report_is_error(self, tmp_path: Path) -> None:
        results = make_pytest_results(
            RunStatus.ERROR,
            ["worker crashed"],
            test_results=_report(3, passed=3),
            summary_text="Collected 3 tests in 0.0 seconds",
        )

        result = _run_with(tmp_path, results)

        assert result.status == "error"
        assert "reported an error" in result.summary
        assert "worker crashed" in result.summary

    def test_error_no_tests_found_is_skipped(self, tmp_path: Path) -> None:
        problem = "No Tests Found: pytest did not collect any tests"
        results = make_pytest_results(RunStatus.ERROR, [problem])

        result = _run_with(tmp_path, results)

        assert result.status == "skipped"
        assert result.summary == problem
        assert "reported an error" not in result.summary

    def test_suspicious_is_ok_not_verified(self, tmp_path: Path) -> None:
        results = make_pytest_results(
            RunStatus.SUSPICIOUS,
            test_results=_report(5),
            summary_text="Collected 5 tests in 0.0 seconds",
        )

        result = _run_with(tmp_path, results)

        assert result.status == "ok"
        assert "Not verified" in result.summary

    def test_suspicious_counts_selected_tests(self, tmp_path: Path) -> None:
        report = _report(4)
        report.summary.deselected = 3
        results = make_pytest_results(
            RunStatus.SUSPICIOUS,
            test_results=report,
            summary_text="",
        )

        result = _run_with(tmp_path, results)

        assert result.status == "ok"
        assert "Collected 1 tests" in result.summary
        assert "Not verified" in result.summary

    def test_failed_with_failing_test_is_findings(self, tmp_path: Path) -> None:
        failing = Test(
            nodeid="tests/test_a.py::test_x", lineno=1, keywords=[], outcome="failed"
        )
        results = make_pytest_results(
            RunStatus.FAILED,
            test_results=_report(1, failed=1, tests=[failing]),
            summary_text="Collected 1 tests in 0.0 seconds",
        )

        result = _run_with(tmp_path, results)

        assert result.status == "findings"
        assert [f.key for f in result.findings] == ["tests/test_a.py::test_x"]
        assert result.summary == "Collected 1 tests in 0.0 seconds"

    def test_failed_with_failing_test_and_collectors_shows_both(
        self, tmp_path: Path
    ) -> None:
        failing = Test(
            nodeid="tests/test_a.py::test_x", lineno=1, keywords=[], outcome="failed"
        )
        problem = "E   ImportError: no module named 'missing'"
        report = _report(
            2,
            failed=1,
            tests=[failing],
            collectors=[
                Collector(nodeid=nodeid, outcome="failed", result=[], longrepr=problem)
                for nodeid in ("tests/test_b.py", "tests/test_c.py")
            ],
        )
        grouped = group_failed_collectors(report)
        summary_text = "Collected 2 tests in 0.0 seconds"
        results = make_pytest_results(
            RunStatus.FAILED,
            grouped,
            test_results=report,
            summary_text=summary_text,
        )

        result = _run_with(tmp_path, results)

        assert result.status == "findings"
        assert [f.key for f in result.findings] == ["tests/test_a.py::test_x"]
        assert result.summary.startswith(
            f"{summary_text}\n\n2 collectors failed (1 distinct error)\n\n{problem}\n"
        )
        assert "same error in 1 more collector: tests/test_c.py" in result.summary

    def test_failed_without_failing_tests_is_error(self, tmp_path: Path) -> None:
        collector = Collector(
            nodeid="tests/test_broken.py",
            outcome="failed",
            result=[],
            longrepr="ImportError: no module named 'missing'",
        )
        summary_text = "Collected 0 tests in 0.0 seconds"
        results = make_pytest_results(
            RunStatus.FAILED,
            ["ImportError: no module named 'missing'"],
            test_results=_report(0, collectors=[collector]),
            summary_text=summary_text,
        )

        result = _run_with(tmp_path, results)

        assert result.status == "error"
        assert summary_text in result.summary
        assert "ImportError: no module named 'missing'" in result.summary

    def test_failed_without_failing_tests_counts_collectors(
        self, tmp_path: Path
    ) -> None:
        problem = "ImportError: no module named 'missing'"
        collector = Collector(
            nodeid="tests/test_broken.py",
            outcome="failed",
            result=[],
            longrepr=problem,
        )
        results = make_pytest_results(
            RunStatus.FAILED,
            [problem],
            test_results=_report(0, collectors=[collector]),
            summary_text="Collected 0 tests in 0.0 seconds",
        )

        result = _run_with(tmp_path, results)

        assert result.status == "error"
        count_line = "1 collector failed (1 distinct error)"
        assert result.summary.index(count_line) < result.summary.index(problem)

    def test_failed_without_collector_keeps_summary(self, tmp_path: Path) -> None:
        results = make_pytest_results(
            RunStatus.FAILED,
            ["some problem"],
            test_results=_report(0),
            summary_text="Collected 0 tests in 0.0 seconds",
        )

        result = _run_with(tmp_path, results)

        assert result.status == "error"
        assert result.summary == ("Collected 0 tests in 0.0 seconds\n\nsome problem\n")

    def test_passed_is_ok(self, tmp_path: Path) -> None:
        results = make_pytest_results(
            RunStatus.PASSED,
            test_results=_report(2, passed=2),
            summary_text="Collected 2 tests in 0.0 seconds",
        )

        result = _run_with(tmp_path, results)

        assert result.status == "ok"
        assert result.findings == []
