"""Tests for PythonToolkit's `test` action, at each depth."""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from mcp_coder_utils.toolkit import ActionRequest, ActionResult

from mcp_tools_py.code_checker_pytest.coverage_store import start_coverage_run
from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    ErrorContext,
    PytestReport,
    Summary,
    Test,
)
from mcp_tools_py.code_checker_pytest.reporting import group_failed_collectors
from mcp_tools_py.code_checker_pytest.verdict import (
    XDIST_HINT,
    RunStatus,
    RunVerdict,
)
from mcp_tools_py.toolkit import UNATTENDED_EXCLUDED_MARKERS, PythonToolkit
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
        assert "test_fail.py::test_fails" in result.fix_text

    def test_no_tests_collected_is_skipped(self, tmp_path: Path) -> None:
        _write_empty_project(tmp_path)
        request = ActionRequest(
            action="test", depth="quick", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "skipped"
        assert result.findings == []

    def test_every_module_failing_to_import_is_findings(self, tmp_path: Path) -> None:
        (tmp_path / "tests").mkdir()
        for name in ("test_a.py", "test_b.py"):
            (tmp_path / "tests" / name).write_text(
                "import module_that_does_not_exist\n"
            )
        request = ActionRequest(
            action="test", depth="standard", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "findings"
        keys = sorted(f.key for f in result.findings)
        assert len(keys) == 2
        assert keys[0].endswith("test_a.py")
        assert keys[1].endswith("test_b.py")
        assert all("module_that_does_not_exist" in f.message for f in result.findings)

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

    def test_unknown_action_is_error(self, tmp_path: Path) -> None:
        request = ActionRequest(
            action="bogus", depth="quick", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "error"
        assert "bogus" in result.summary

    @pytest.mark.parametrize(
        ("action", "depth"),
        [("test", "bogus"), ("format", "quick"), ("check", "apply")],
    )
    def test_undeclared_depth_is_error(
        self, tmp_path: Path, action: str, depth: str
    ) -> None:
        request = ActionRequest(
            action=action, depth=depth, project_dir=tmp_path, params={}
        )

        with patch("mcp_tools_py.toolkit._build_context", side_effect=AssertionError):
            result = PythonToolkit().run(request)

        assert result.status == "error"
        assert depth in result.summary


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


class TestRunTestUnattended:
    """`unattended` deselects the LLM/CI-integration markers."""

    def test_unattended_passes_markers_and_strict_markers_off(
        self, tmp_path: Path
    ) -> None:
        results = make_pytest_results(
            RunStatus.PASSED,
            test_results=_report(1, passed=1),
            summary_text="Collected 1 tests in 0.0 seconds",
        )
        request = ActionRequest(
            action="test", depth="unattended", project_dir=tmp_path, params={}
        )

        with patch(
            "mcp_tools_py.toolkit.check_code_with_pytest", return_value=results
        ) as mock_pytest:
            result = PythonToolkit().run(request)

        assert result.status == "ok"
        kwargs = mock_pytest.call_args.kwargs
        assert kwargs["markers"] == UNATTENDED_EXCLUDED_MARKERS
        assert kwargs["extra_args"] == ["-o", "strict_markers=false"]

    def test_unattended_in_strict_marker_project_is_ok(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.pytest.ini_options]\naddopts = "--strict-markers"\n'
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_mixed.py").write_text(
            "import pytest\n\n\n"
            "def test_ok():\n    assert True\n\n\n"
            "@pytest.mark.llm_integration\n"
            "def test_llm():\n    assert False\n"
        )
        request = ActionRequest(
            action="test", depth="unattended", project_dir=tmp_path, params={}
        )

        result = PythonToolkit().run(request)

        assert result.status == "ok"


def _passed_results() -> dict[str, Any]:
    return make_pytest_results(
        RunStatus.PASSED,
        test_results=_report(1, passed=1),
        summary_text="Collected 1 tests in 0.0 seconds",
    )


def _pytest_timeout(tmp_path: Path, depth: str) -> int:
    request = ActionRequest(action="test", depth=depth, project_dir=tmp_path, params={})
    with patch(
        "mcp_tools_py.toolkit.check_code_with_pytest", return_value=_passed_results()
    ) as mock_pytest:
        result = PythonToolkit().run(request)
    assert result.status == "ok"
    timeout: int = mock_pytest.call_args.kwargs["timeout_seconds"]
    return timeout


class TestRunTestTimeout:
    """Non-quick depths default pytest to the long timeout."""

    @pytest.mark.parametrize("depth", ["standard", "unattended"])
    def test_non_quick_depth_uses_long_timeout(
        self, tmp_path: Path, depth: str
    ) -> None:
        assert _pytest_timeout(tmp_path, depth) == 1800

    def test_quick_uses_default_timeout(self, tmp_path: Path) -> None:
        assert _pytest_timeout(tmp_path, "quick") == 300

    def test_pytest_timeout_setting_wins(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mcp-tools-py]\npytest-timeout = 42\n"
        )

        assert _pytest_timeout(tmp_path, "standard") == 42

    def test_check_timeout_setting_wins(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.mcp-tools-py]\ncheck-timeout = 77\n"
        )

        assert _pytest_timeout(tmp_path, "standard") == 77

    def test_full_uses_long_timeout_for_pytest_and_coverage_run(
        self, tmp_path: Path
    ) -> None:
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
            patch(
                "mcp_tools_py.toolkit.start_coverage_run", wraps=start_coverage_run
            ) as mock_start,
            patch("mcp_tools_py.toolkit.finish_coverage_run", return_value=None),
        ):
            result = PythonToolkit().run(request)

        assert result.status == "ok"
        assert mock_pytest.call_args.kwargs["timeout_seconds"] == 1800
        assert mock_start.call_args.args[-1] == 1800


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
        assert [f.key for f in result.findings] == [
            "tests/test_a.py::test_x",
            "tests/test_b.py",
            "tests/test_c.py",
        ]
        assert result.summary.startswith(
            f"{summary_text}\n\n2 collectors failed (1 distinct error)\n\n{problem}\n"
        )
        assert "same error in 1 more collector: tests/test_c.py" in result.summary

    def test_failed_without_failing_tests_is_findings(self, tmp_path: Path) -> None:
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

        assert result.status == "findings"
        assert [f.key for f in result.findings] == ["tests/test_broken.py"]
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

        assert result.status == "findings"
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


class TestRunTestPathsNote:
    """The test_paths_note of the result leads the summary of every return."""

    def test_skipped(self, tmp_path: Path) -> None:
        results = {
            **_error_results(5, "", []),
            "verdict": RunVerdict(RunStatus.ERROR, ["No Tests Found: none"], 5),
            "test_paths_note": "NOTE",
        }

        result = _run_with(tmp_path, results)

        assert result.status == "skipped"
        assert result.summary.startswith("NOTE")

    def test_error(self, tmp_path: Path) -> None:
        results = {
            **_error_results(3, "INTERNALERROR> boom", []),
            "test_paths_note": "NOTE",
        }

        result = _run_with(tmp_path, results)

        assert result.status == "error"
        assert result.summary.startswith("NOTE")

    def test_failed_without_findings(self, tmp_path: Path) -> None:
        results = {
            **_failed_results([_collector("tests/test_x.py", outcome="passed")]),
            "test_paths_note": "NOTE",
        }

        result = _run_with(tmp_path, results)

        assert result.status == "error"
        assert result.summary.startswith("NOTE")

    def test_passed(self, tmp_path: Path) -> None:
        results = {**_passed_results(), "test_paths_note": "NOTE"}

        result = _run_with(tmp_path, results)

        assert result.status == "ok"
        assert result.summary.startswith("NOTE")


def _collector(
    nodeid: str, longrepr: str | None = "E   ImportError: boom", outcome: str = "failed"
) -> Collector:
    return Collector(nodeid=nodeid, outcome=outcome, result=[], longrepr=longrepr)


def _error_results(
    exit_code: int, output: str, collectors: list[Collector]
) -> dict[str, Any]:
    report = _report(0, collectors=collectors)
    report.error_context = ErrorContext(
        exit_code=exit_code,
        exit_code_meaning="",
        error_message=output,
        suggestion="",
    )
    return {
        "verdict": RunVerdict(RunStatus.ERROR, ["problem"], exit_code),
        "summary_text": "Collected 0 tests in 0.0 seconds",
        "test_results": report,
    }


def _failed_results(collectors: list[Collector]) -> dict[str, Any]:
    return make_pytest_results(
        RunStatus.FAILED,
        ["problem"],
        test_results=_report(0, collectors=collectors),
        summary_text="Collected 0 tests in 0.0 seconds",
    )


class TestRunTestCollectors:
    """Failed collectors become findings."""

    @pytest.mark.parametrize(
        ("exit_code", "output"),
        [(2, "Interrupted: 1 error during collection"), (1, "")],
    )
    def test_collection_error_is_findings(
        self, tmp_path: Path, exit_code: int, output: str
    ) -> None:
        results = _error_results(
            exit_code, output, [_collector("tests/test_broken.py")]
        )

        result = _run_with(tmp_path, results)

        assert result.status == "findings"
        assert [f.key for f in result.findings] == ["tests/test_broken.py"]
        assert result.findings[0].path == "tests/test_broken.py"
        assert result.findings[0].message == "E   ImportError: boom"

    @pytest.mark.parametrize(
        ("exit_code", "output"),
        [(3, "INTERNALERROR> boom"), (2, "KeyboardInterrupt")],
    )
    def test_unrelated_error_stays_error(
        self, tmp_path: Path, exit_code: int, output: str
    ) -> None:
        results = _error_results(
            exit_code, output, [_collector("tests/test_broken.py")]
        )

        result = _run_with(tmp_path, results)

        assert result.status == "error"
        assert result.findings == []

    def test_empty_longrepr_is_collection_failed(self, tmp_path: Path) -> None:
        results = _failed_results([_collector("tests/test_broken.py", longrepr="")])

        result = _run_with(tmp_path, results)

        assert [f.message for f in result.findings] == ["collection failed"]

    def test_same_node_id_twice_is_one_finding(self, tmp_path: Path) -> None:
        results = _failed_results(
            [_collector("tests/test_broken.py"), _collector("tests/test_broken.py")]
        )

        result = _run_with(tmp_path, results)

        assert [f.key for f in result.findings] == ["tests/test_broken.py"]

    @pytest.mark.parametrize("outcome", ["skipped", "passed"])
    def test_non_failed_collector_is_no_finding(
        self, tmp_path: Path, outcome: str
    ) -> None:
        results = _failed_results([_collector("tests/test_x.py", outcome=outcome)])

        result = _run_with(tmp_path, results)

        assert result.status == "error"
        assert result.findings == []

    def test_xdist_collectors_are_one_finding(self, tmp_path: Path) -> None:
        longrepr = "Different tests were collected between gw0 and gw1."
        results = _failed_results(
            [_collector("gw0", longrepr), _collector("gw1", longrepr)]
        )

        result = _run_with(tmp_path, results)

        assert result.status == "findings"
        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.key == "pytest|collection|xdist"
        assert finding.path is None
        assert result.fix_text.count(XDIST_HINT) == 1
