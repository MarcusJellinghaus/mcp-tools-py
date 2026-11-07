"""Tests for the pytest run verdict classifier and its text helpers."""

from typing import List, Optional

import pytest

from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    CollectorResult,
    ErrorContext,
    PytestReport,
    Summary,
)
from mcp_tools_py.code_checker_pytest.reporting import MAX_OUTPUT_LINES, XDIST_MARKER
from mcp_tools_py.code_checker_pytest.verdict import (
    XDIST_HINT,
    RunStatus,
    RunVerdict,
    classify_run,
    format_collect_only_text,
    format_collection_problems,
    format_error_text,
    format_suspicious_text,
)


def _summary(collected: int = 0, **counts: Optional[int]) -> Summary:
    return Summary(collected=collected, total=collected, **counts)


def _ctx(exit_code: int, error_message: str = "") -> ErrorContext:
    return ErrorContext(
        exit_code=exit_code,
        exit_code_meaning="",
        error_message=error_message,
        suggestion="",
    )


def _collector(longrepr: str, outcome: str = "failed") -> Collector:
    return Collector(nodeid="tests", outcome=outcome, result=[], longrepr=longrepr)


def _report(
    summary: Optional[Summary] = None,
    collectors: Optional[List[Collector]] = None,
    error_context: Optional[ErrorContext] = None,
) -> PytestReport:
    return PytestReport(
        created=0.0,
        duration=1.0,
        exitcode=error_context.exit_code if error_context else 0,
        root="/tmp",
        environment={},
        summary=summary or _summary(),
        collectors=collectors,
        error_context=error_context,
    )


@pytest.mark.parametrize(
    "report, expected_status, expected_exit",
    [
        (_report(_summary(3, passed=2, failed=1), error_context=_ctx(1)), "failed", 1),
        (_report(_summary(3, passed=2, error=1), error_context=_ctx(1)), "failed", 1),
        (_report(_summary(3, passed=3), error_context=_ctx(1)), "error", 1),
        (
            _report(
                _summary(0),
                collectors=[_collector("ImportError")],
                error_context=_ctx(2),
            ),
            "error",
            2,
        ),
        (_report(_summary(4, passed=0, failed=None)), "suspicious", 0),
        (_report(_summary(2, skipped=2), error_context=_ctx(0)), "passed", 0),
        (_report(_summary(2, xfailed=2), error_context=_ctx(0)), "passed", 0),
        (_report(_summary(2, passed=2), error_context=_ctx(0)), "passed", 0),
        (_report(_summary(2, passed=2)), "passed", 0),
    ],
    ids=[
        "failures",
        "errors",
        "exit1-no-failures",
        "exit2-failed-collector",
        "no-outcomes",
        "only-skipped",
        "only-xfailed",
        "passing",
        "no-error-context",
    ],
)
def test_classify_run(
    report: PytestReport, expected_status: str, expected_exit: int
) -> None:
    verdict = classify_run(report)
    assert verdict.status is RunStatus(expected_status)
    assert verdict.exit_code == expected_exit


def test_problems_ignore_passed_collectors() -> None:
    report = _report(
        _summary(1, passed=1),
        collectors=[_collector("fine", outcome="passed")],
    )
    assert not classify_run(report).problems


def test_error_message_tail_used_for_error_only_and_capped() -> None:
    message = "\n".join(f"line {i}" for i in range(80))
    verdict = classify_run(_report(_summary(0), error_context=_ctx(3, message)))
    assert verdict.status is RunStatus.ERROR
    assert len(verdict.problems) == 1
    tail = verdict.problems[0].splitlines()
    assert len(tail) == 50
    assert tail[0] == "line 30"
    assert tail[-1] == "line 79"


def test_error_message_tail_not_used_when_other_problems_exist() -> None:
    report = _report(
        _summary(0),
        collectors=[_collector("collector problem")],
        error_context=_ctx(2, "full output"),
    )
    assert classify_run(report).problems == ["collector problem"]


def test_failed_run_ignores_error_message() -> None:
    report = _report(
        _summary(2, passed=1, failed=1), error_context=_ctx(1, "full output")
    )
    verdict = classify_run(report)
    assert verdict.status is RunStatus.FAILED
    assert not verdict.problems


def test_dedup_xdist_marker() -> None:
    collectors = [
        _collector(f"worker gw{i}\n{XDIST_MARKER} between gw0 and gw{i}")
        for i in range(3)
    ]
    report = _report(_summary(0), collectors=collectors, error_context=_ctx(1))
    problems = classify_run(report).problems
    assert len(problems) == 1
    assert "worker gw0" in problems[0]


def test_same_first_line_with_different_last_lines_stay_separate() -> None:
    collectors = [_collector("ImportError: x\nA"), _collector("ImportError: x\nB")]
    report = _report(_summary(0), collectors=collectors, error_context=_ctx(2))
    assert classify_run(report).problems == ["ImportError: x\nA", "ImportError: x\nB"]


def test_format_error_text_truncates_and_keeps_hint() -> None:
    block = "\n".join(f"line {j}" for j in range(MAX_OUTPUT_LINES // 2))
    problems = [f"p{i}\n{block}" for i in range(3)] + [f"{XDIST_MARKER} on gw1"]
    text = format_error_text(None, RunVerdict(RunStatus.ERROR, problems, 1))
    assert "Output truncated" in text
    assert XDIST_HINT in text
    assert text.index("Output truncated") < text.index(XDIST_HINT)


def test_format_error_text_exit2_with_collector_omits_interrupted() -> None:
    report = _report(
        _summary(0), collectors=[_collector("ImportError")], error_context=_ctx(2)
    )
    text = format_error_text(report, classify_run(report))
    assert "interrupted by the user" not in text
    assert "Exit code" not in text
    assert "ImportError" in text


def test_format_error_text_exit1_with_collector_no_failed_test_omits_exit_line() -> (
    None
):
    report = _report(
        _summary(0), collectors=[_collector("ImportError")], error_context=_ctx(1)
    )
    text = format_error_text(report, classify_run(report))
    assert "Exit code" not in text
    assert "some tests failed" not in text
    assert "ImportError" in text


@pytest.mark.parametrize(
    "counts", [{"failed": 1}, {"error": 1}], ids=["failed", "error"]
)
def test_format_error_text_exit1_with_collector_and_failed_test_keeps_exit_line(
    counts: dict[str, int],
) -> None:
    report = _report(
        _summary(2, passed=1, **counts),
        collectors=[_collector("ImportError")],
        error_context=_ctx(1),
    )
    text = format_error_text(report, classify_run(report))
    assert "Exit code 1:" in text


def test_format_error_text_exit1_includes_exit_line() -> None:
    report = _report(_summary(3, passed=3), error_context=_ctx(1, "boom"))
    text = format_error_text(report, classify_run(report))
    assert text.startswith("Pytest run reported an error.")
    assert "Exit code 1:" in text


def test_format_error_text_without_report() -> None:
    verdict = RunVerdict(RunStatus.ERROR, ["Usage Error: x"], 0)
    text = format_error_text(None, verdict)
    assert "did not complete" in text
    assert "Usage Error: x" in text
    assert "Exit code" not in text


def test_format_error_text_includes_counts() -> None:
    report = _report(_summary(3, passed=3), error_context=_ctx(1))
    text = format_error_text(report, classify_run(report))
    assert "Collected 3 tests" in text
    assert "Passed: 3" in text
    assert "did not complete" not in text


def test_format_collection_problems_empty() -> None:
    verdict = RunVerdict(RunStatus.FAILED, [], 1)
    assert format_collection_problems(verdict) == ""


def test_format_collection_problems_xdist_hint_from_collector() -> None:
    report = _report(
        _summary(2, failed=1),
        collectors=[_collector(f"{XDIST_MARKER} on gw1")],
        error_context=_ctx(1),
    )
    text = format_collection_problems(classify_run(report))
    assert text == f"Collection problems:\n{XDIST_HINT}"


def test_format_suspicious_text() -> None:
    text = format_suspicious_text(3)
    assert "Collected 3 tests" in text
    assert "Not verified" in text


def test_package_exports() -> None:
    # pylint: disable=import-outside-toplevel
    from mcp_tools_py import code_checker_pytest

    assert code_checker_pytest.RunStatus is RunStatus
    assert code_checker_pytest.RunVerdict is RunVerdict
    assert code_checker_pytest.classify_run is classify_run


def test_format_suspicious_text_subtracts_deselected() -> None:
    assert "Collected 1 tests" in format_suspicious_text(4, 3)


def _collect_only_report(
    ids: List[str], collected: int, deselected: Optional[int] = None
) -> PytestReport:
    """Build a collect-only report whose one collector lists ``ids``."""
    collector = Collector(
        nodeid="tests/test_x.py",
        outcome="passed",
        result=[CollectorResult(nodeid=nodeid, type="Function") for nodeid in ids],
    )
    summary = Summary(collected=collected, total=0, deselected=deselected)
    return _report(summary, collectors=[collector])


def test_format_collect_only_text_with_deselected() -> None:
    report = _collect_only_report(["tests/test_x.py::test_a"], 4, deselected=3)
    lines = format_collect_only_text(report).splitlines()
    assert lines == [
        "Collected 1 test (3 deselected) in 1.00 seconds. No tests were run.",
        "tests/test_x.py::test_a",
    ]


def test_format_collect_only_text_without_deselected() -> None:
    ids = ["tests/test_x.py::test_a", "tests/test_x.py::test_b"]
    text = format_collect_only_text(_collect_only_report(ids, 2))
    assert text.splitlines()[0] == (
        "Collected 2 tests in 1.00 seconds. No tests were run."
    )
    assert "deselected" not in text


def test_format_collect_only_text_truncates_ids() -> None:
    ids = [f"tests/test_x.py::test_{n}" for n in range(400)]
    text = format_collect_only_text(_collect_only_report(ids, 400))
    assert text.splitlines()[0].startswith("Collected 400 tests")
    assert f"[Output truncated at {MAX_OUTPUT_LINES} lines" in text


def test_format_collect_only_text_without_collectors() -> None:
    report = _report(Summary(collected=2, total=0))
    assert format_collect_only_text(report) == (
        "Collected 2 tests in 1.00 seconds. No tests were run.\n"
    )
