"""Reply-level tests for the flag notes and the tail block of run_pytest_check."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.code_checker_pytest.models import PytestReport, StageInfo, Summary
from mcp_tools_py.code_checker_pytest.models import Test as ReportTest
from mcp_tools_py.code_checker_pytest.models import Warning as ReportWarning
from mcp_tools_py.code_checker_pytest.report_extras import (
    DEFAULT_DURATIONS_MIN,
    SNAPSHOT_NOTE,
    ReportFlags,
    has_tests,
    report_tail,
)
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from tests._pytest_results import make_pytest_results
from tests.conftest import make_environment_info

_PYTEST_TOOL = "mcp_tools_py.checker_tools.pytest_tool"
_GET_ENVIRONMENT_INFO = "mcp_tools_py.utils.tool_context.get_environment_info"
_HINT_SW = (
    'For details: extra_args=["-rsw", "--durations=5"]'
    " (skip reasons, warnings — counted only by default, slowest tests)"
)
_NO_EFFECT_X = (
    "-rx has no effect here; supported: -rs, -rw"
    " (failures are always shown; -s shows passing-test output)"
)


@pytest.fixture
def run_pytest_check(tmp_path: Path, all_modules_importable: Any) -> Iterator[Any]:
    """run_pytest_check over tmp_path, with pytest-json-report reported installed."""
    with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
        mock_tool = MagicMock()
        mock_fastmcp.return_value.tool.return_value = mock_tool

        from mcp_tools_py.server import (  # pylint: disable=import-outside-toplevel
            ToolServer,
        )

        with patch.object(
            ToolServer, "_warn_missing_console_scripts", return_value=None
        ):
            ToolServer(project_dir=tmp_path)

    tools = {f.__name__: f for call in mock_tool.call_args_list for f in [call[0][0]]}
    info = make_environment_info(distributions={"pytest-json-report": "1.5.0"})
    with patch(_GET_ENVIRONMENT_INFO, return_value=info):
        yield tools["run_pytest_check"]


def _pyproject(project_dir: Path, *lines: str) -> None:
    body = "\n".join(lines)
    (project_dir / "pyproject.toml").write_text(
        f"[tool.pytest.ini_options]\n{body}\n", encoding="utf-8"
    )


def _passed_test(
    nodeid: str = "tests/test_a.py::test_ok", call: float = 0.0
) -> ReportTest:
    return ReportTest(
        nodeid=nodeid,
        lineno=1,
        keywords=[],
        outcome="passed",
        setup=StageInfo(duration=0.0, outcome="passed"),
        call=StageInfo(duration=call, outcome="passed"),
        teardown=StageInfo(duration=0.0, outcome="passed"),
    )


def _failed_test(nodeid: str = "tests/test_a.py::test_bad") -> ReportTest:
    return ReportTest(
        nodeid=nodeid,
        lineno=1,
        keywords=[],
        outcome="failed",
        setup=StageInfo(duration=0.0, outcome="passed"),
        call=StageInfo(duration=0.0, outcome="failed", longrepr="AssertionError: boom"),
        teardown=StageInfo(duration=0.0, outcome="passed"),
    )


def _skipped_test(root: Path, nodeid: str = "tests/test_a.py::test_skip") -> ReportTest:
    longrepr = str((str(root / "tests" / "test_a.py"), 7, "Skipped: no db"))
    return ReportTest(
        nodeid=nodeid,
        lineno=1,
        keywords=[],
        outcome="skipped",
        setup=StageInfo(duration=0.0, outcome="passed"),
        call=StageInfo(duration=0.0, outcome="skipped", longrepr=longrepr),
    )


def _warning(root: Path) -> ReportWarning:
    return ReportWarning(
        message="old api",
        category="DeprecationWarning",
        when="runtest",
        filename=str(root / "tests" / "test_a.py"),
        lineno=3,
    )


def _report(
    root: Path,
    tests: list[ReportTest] | None = None,
    warnings: list[ReportWarning] | None = None,
) -> PytestReport:
    tests = tests if tests is not None else [_passed_test()]
    return PytestReport(
        created=0.0,
        duration=0.5,
        exitcode=0,
        root=str(root),
        environment={},
        summary=Summary(collected=len(tests), total=len(tests)),
        tests=tests,
        warnings=warnings,
    )


def _results(
    report: PytestReport | None,
    status: RunStatus = RunStatus.PASSED,
    summary_text: str = "✅ Passed: 1",
    **fields: Any,
) -> dict[str, Any]:
    return make_pytest_results(
        status,
        fields.pop("problems", None),
        test_results=report,
        summary_text=summary_text,
        summary={"passed": 1, "collected": 1},
        exit_code=fields.pop("exit_code", 0),
        **fields,
    )


def _call(run_pytest_check: Any, results: dict[str, Any], **kwargs: Any) -> str:
    with patch(f"{_PYTEST_TOOL}.check_code_with_pytest", return_value=results):
        reply: str = run_pytest_check(**kwargs)
    return reply


def _flags(**changes: Any) -> ReportFlags:
    fields: dict[str, Any] = {
        "letters": frozenset(),
        "r_label": None,
        "no_effect": "",
        "durations": None,
        "durations_min": DEFAULT_DURATIONS_MIN,
        "durations_min_in_call": False,
        "show_capture": None,
        "snapshot_update": False,
        "disable_warnings": False,
        **changes,
    }
    return ReportFlags(**fields)


class TestHasTests:
    """has_tests is decision 19's predicate."""

    def test_report_with_tests(self, tmp_path: Path) -> None:
        assert has_tests(_report(tmp_path), collect_only=False)

    def test_no_report(self) -> None:
        assert not has_tests(None, collect_only=False)

    def test_report_without_tests(self, tmp_path: Path) -> None:
        assert not has_tests(_report(tmp_path, tests=[]), collect_only=False)

    def test_collect_only(self, tmp_path: Path) -> None:
        assert not has_tests(_report(tmp_path), collect_only=True)


class TestReportTail:
    """report_tail puts the sections first and the hint last."""

    def test_empty_when_nothing_to_show(self, tmp_path: Path) -> None:
        assert report_tail(_report(tmp_path), _flags(), 100, 10_000) == ""

    def test_sections_then_hint(self, tmp_path: Path) -> None:
        report = _report(
            tmp_path,
            tests=[_passed_test(), _skipped_test(tmp_path)],
            warnings=[_warning(tmp_path)],
        )

        tail = report_tail(report, _flags(letters=frozenset({"s"})), 100, 10_000)

        lines = tail.splitlines()
        assert lines[0] == "Skip reasons:"
        assert lines[1] == "SKIPPED [1] tests/test_a.py:7: no db"
        assert lines[-1].startswith('For details: extra_args=["-rsw"')

    def test_hint_kept_when_one_line_is_left(self, tmp_path: Path) -> None:
        report = _report(
            tmp_path,
            tests=[_passed_test(), _skipped_test(tmp_path)],
            warnings=[_warning(tmp_path)],
        )

        tail = report_tail(report, _flags(letters=frozenset({"s"})), 1, 10_000)

        assert tail.startswith("For details:")
        assert len(tail.splitlines()) == 1

    def test_nothing_when_no_line_is_left(self, tmp_path: Path) -> None:
        report = _report(tmp_path, warnings=[_warning(tmp_path)])

        assert report_tail(report, _flags(), 0, 10_000) == ""


def test_clean_run_is_one_line(run_pytest_check: Any, tmp_path: Path) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')

    reply = _call(run_pytest_check, _results(_report(tmp_path)))

    assert reply == "Pytest check completed. ✅ Passed: 1"


def test_clean_run_with_addopts_ra_is_one_line(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'addopts = "-ra"')

    reply = _call(run_pytest_check, _results(_report(tmp_path)))

    assert reply == "Pytest check completed. ✅ Passed: 1"


def test_skips_and_warnings_get_summary_blank_line_hint(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')
    report = _report(
        tmp_path,
        tests=[_passed_test(), _skipped_test(tmp_path)],
        warnings=[_warning(tmp_path)],
    )

    reply = _call(
        run_pytest_check, _results(report, summary_text="✅ Passed: 1 | ⏭️ Skipped: 1")
    )

    assert reply.splitlines() == [
        "Pytest check completed. ✅ Passed: 1 | ⏭️ Skipped: 1 | ⚠️ Warnings: 1",
        "",
        _HINT_SW,
    ]


def test_addopts_durations_shows_section_on_clean_run(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'addopts = "--durations=10"')
    report = _report(tmp_path, tests=[_passed_test(call=0.5)])

    reply = _call(run_pytest_check, _results(report))

    assert reply.splitlines() == [
        "Pytest check completed. ✅ Passed: 1",
        "",
        "Slowest 10 durations:",
        "0.50s call tests/test_a.py::test_ok",
        "(2 durations < 0.005s hidden; pass --durations-min=0 to show them.)",
    ]


def test_snapshot_update_note_on_report_with_tests(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')

    reply = _call(
        run_pytest_check,
        _results(_report(tmp_path)),
        extra_args=["--snapshot-update"],
    )

    lines = reply.splitlines()
    assert lines[0] == SNAPSHOT_NOTE
    assert lines.index(SNAPSHOT_NOTE) < lines.index(
        "Pytest check completed. ✅ Passed: 1"
    )


def test_snapshot_update_from_addopts_note(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'addopts = "--snapshot-update"')

    reply = _call(run_pytest_check, _results(_report(tmp_path)))

    assert SNAPSHOT_NOTE in reply.splitlines()


def test_snapshot_update_on_error_without_tests_gets_no_note(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')
    results = _results(
        None,
        RunStatus.ERROR,
        summary_text="",
        problems=["Usage Error: unrecognized arguments: --snapshot-update"],
        exit_code=4,
    )

    reply = _call(run_pytest_check, results, extra_args=["--snapshot-update"])

    assert SNAPSHOT_NOTE not in reply


def test_failed_run_keeps_failures_before_the_tail(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')
    report = _report(
        tmp_path,
        tests=[_failed_test(), _skipped_test(tmp_path)],
        warnings=[_warning(tmp_path)],
    )
    results = _results(report, RunStatus.FAILED, summary_text="❌ Failed: 1")

    reply = _call(run_pytest_check, results)

    assert "AssertionError: boom" in reply
    assert reply.splitlines()[-1] == _HINT_SW
    assert reply.index("AssertionError: boom") < reply.index("For details:")


def test_collect_only_gets_no_tail(run_pytest_check: Any, tmp_path: Path) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')
    report = _report(
        tmp_path, tests=[_skipped_test(tmp_path)], warnings=[_warning(tmp_path)]
    )
    results = _results(report, RunStatus.SUSPICIOUS, summary_text="")

    reply = _call(run_pytest_check, results, extra_args=["--collect-only", "-rsx"])

    assert "For details:" not in reply
    assert "no skipped tests" not in reply
    assert "has no effect here" not in reply


def test_rx_note_when_passed_in_the_call(run_pytest_check: Any, tmp_path: Path) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')

    reply = _call(run_pytest_check, _results(_report(tmp_path)), extra_args=["-rx"])

    assert _NO_EFFECT_X in reply.splitlines()


def test_rx_from_addopts_gets_no_note(run_pytest_check: Any, tmp_path: Path) -> None:
    _pyproject(tmp_path, 'addopts = "-rx"')

    reply = _call(run_pytest_check, _results(_report(tmp_path)))

    assert reply == "Pytest check completed. ✅ Passed: 1"


def test_call_rs_on_clean_run_prints_empty_line(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')

    reply = _call(run_pytest_check, _results(_report(tmp_path)), extra_args=["-ra"])

    assert reply.splitlines() == [
        "Pytest check completed. ✅ Passed: 1",
        "",
        "-ra: no skipped tests, no warnings.",
    ]


def test_show_capture_reaches_failure_blocks(
    run_pytest_check: Any, tmp_path: Path
) -> None:
    _pyproject(tmp_path, 'markers = ["slow"]')
    failed = _failed_test()
    assert failed.call is not None
    failed.call.stdout = "printed text"
    report = _report(tmp_path, tests=[failed])
    results = _results(report, RunStatus.FAILED, summary_text="❌ Failed: 1")

    shown = _call(run_pytest_check, results)
    hidden = _call(run_pytest_check, results, extra_args=["--show-capture=no"])

    assert "printed text" in shown
    assert "printed text" not in hidden
