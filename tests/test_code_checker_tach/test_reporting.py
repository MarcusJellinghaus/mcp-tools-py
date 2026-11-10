"""Tests for code_checker_tach.reporting module."""

from mcp_tools_py.code_checker_tach.parsers import TachDiagnostic, parse_tach_json
from mcp_tools_py.code_checker_tach.reporting import TACH_HINT, format_tach_report
from mcp_tools_py.code_checker_tach.runners import TachResult
from mcp_tools_py.utils.report_budget import SUMMARY_HINT, TOOL_LINES
from tests.test_code_checker_tach.test_parsers import (
    GLOBAL_WARNING_JSON,
    VIOLATIONS_JSON,
)


def _error(file: str, line: int, usage: str, dependency: str) -> TachDiagnostic:
    kind = "UndeclaredDependency"
    message = f"{kind}: {usage} -> {dependency}"
    return TachDiagnostic(file, line, "error", kind, usage, dependency, message)


def _parsed(text: str, return_code: int) -> TachResult:
    diagnostics = parse_tach_json(text)
    assert diagnostics is not None
    return TachResult(None, return_code, diagnostics, None)


def test_error_is_reported() -> None:
    result = TachResult("tach check timed out after 5 seconds.", -1, [], None)

    assert format_tach_report(result) == "tach check timed out after 5 seconds."


def test_no_output() -> None:
    assert format_tach_report(TachResult(None, 0, [], None)) == (
        "tach check passed (no output)."
    )
    assert format_tach_report(TachResult(None, 1, [], None)) == (
        "tach check failed (exit code 1, no output)."
    )


def test_raw_output_passes_through() -> None:
    result = TachResult(None, 1, [], "Failed to parse project config")

    assert format_tach_report(result) == (
        "tach check failed:\nFailed to parse project config"
    )


def test_errors_detailed_first_and_warnings_summarised() -> None:
    report = format_tach_report(_parsed(VIOLATIONS_JSON, 1))

    sections = report.split("\n\n")
    assert sections[0] == (
        "tach check failed\ntach found 2 issues across 1 rule, plus 1 warning"
    )
    assert "UndeclaredDependency: a -> b" in sections[1]
    assert "- a/x.py: 1, 2 — UndeclaredDependency: a -> b" in sections[1]
    assert "[warning] DeprecatedDependency: c -> b: 1 occurrence" in sections[2]


def test_warnings_only_passes() -> None:
    report = format_tach_report(_parsed(GLOBAL_WARNING_JSON, 0))

    assert report.startswith("tach check passed with 1 warning")
    assert "- (global) — NoFirstPartyImportsFound" in report


def test_max_issues_zero_lists_every_rule() -> None:
    report = format_tach_report(_parsed(VIOLATIONS_JSON, 1), max_issues=0)

    assert "Locations:" not in report
    assert "- [error] UndeclaredDependency: a -> b: 2 occurrences" in report
    assert "- [warning] DeprecatedDependency: c -> b: 1 occurrence" in report


def test_budget_many_module_pairs_end_with_summary_hint() -> None:
    diagnostics = [
        _error(f"src/m{i % 40}/f{i % 7}.py", i, f"m{i % 40}", f"d{i % 40}")
        for i in range(500)
    ]

    report = format_tach_report(TachResult(None, 1, diagnostics, None))

    assert len(report.splitlines()) < TOOL_LINES
    assert report.endswith(SUMMARY_HINT)


def test_location_overflow_ends_with_tach_hint() -> None:
    diagnostics = [_error(f"src/f{i}.py", i, "a", "b") for i in range(30)]

    report = format_tach_report(TachResult(None, 1, diagnostics, None))

    overflow = [line for line in report.splitlines() if line.startswith("... and ")]
    assert overflow
    assert all(line.endswith(TACH_HINT) for line in overflow)
    assert "target_directories" not in report
