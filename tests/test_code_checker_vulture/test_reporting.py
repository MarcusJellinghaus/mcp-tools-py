"""Tests for code_checker_vulture.reporting module."""

from mcp_tools_py.code_checker_vulture.parsers import VultureMessage
from mcp_tools_py.code_checker_vulture.reporting import (
    VULTURE_HINT,
    format_vulture_report,
)
from mcp_tools_py.code_checker_vulture.runners import VultureResult
from mcp_tools_py.utils.report_budget import SUMMARY_HINT, TOOL_LINES

_KINDS = [
    "unused import",
    "unused function",
    "unused class",
    "unused method",
    "unused variable",
    "unused attribute",
]


def _message(
    kind: str, name: str | None, file: str = "src/a.py", line: int = 1, conf: int = 60
) -> VultureMessage:
    message = f"{kind} '{name}'" if name else kind
    return VultureMessage(file, line, kind, name, message, conf)


def test_error_is_reported() -> None:
    result = VultureResult("vulture timed out after 5 seconds.", [], [])

    assert format_vulture_report(result) == "vulture timed out after 5 seconds."


def test_no_issues() -> None:
    assert format_vulture_report(VultureResult(None, [], [])) == (
        "vulture found no issues."
    )


def test_whitelist_output_passes_through_raw() -> None:
    raw = [
        "_.foo  # unused function (src/a.py:12)",
        "_.bar  # unused variable (src/b.py:3)",
    ]

    assert format_vulture_report(VultureResult(None, [], raw)) == "\n".join(raw)


def test_top_kind_is_detailed_and_rest_summarised() -> None:
    messages = [
        _message("unused import", "os", conf=90),
        _message("unused function", "f", line=3),
        _message("unused function", "g", line=4),
    ]

    report = format_vulture_report(VultureResult(None, messages, []))

    assert report.startswith("vulture found 3 issues across 2 rules")
    detail, summary = report.split("\n\n")[1:]
    assert "unused import" in detail
    assert "src/a.py: 1 — unused import 'os'" in detail
    assert "unused function: 2 occurrences" in summary


def test_max_issues_zero_lists_every_kind() -> None:
    messages = [_message(kind, "x") for kind in _KINDS]

    report = format_vulture_report(VultureResult(None, messages, []), max_issues=0)

    assert "Locations:" not in report
    for kind in _KINDS:
        assert f"- {kind}: 1 occurrence" in report


def test_unparsed_lines_are_appended() -> None:
    result = VultureResult(None, [_message("unused import", "os")], ["Warning: x"])

    report = format_vulture_report(result)

    assert report.endswith("Unparsed vulture output:\nWarning: x")


def test_budget_many_locations_end_with_vulture_hint() -> None:
    messages = [
        _message(_KINDS[i % 6], f"name{i}", file=f"src/m{i % 100}.py", line=i)
        for i in range(2000)
    ]

    report = format_vulture_report(VultureResult(None, messages, []), max_issues=6)

    lines = report.splitlines()
    assert len(lines) < TOOL_LINES
    overflow = [line for line in lines if line.startswith("... and ")]
    assert overflow
    assert all(line.endswith(VULTURE_HINT) for line in overflow)


def test_budget_many_kinds_end_with_summary_hint() -> None:
    messages = [
        _message(f"unreachable code after 'stmt{i}'", None, line=i) for i in range(30)
    ]

    report = format_vulture_report(VultureResult(None, messages, []))

    assert len(report.splitlines()) < TOOL_LINES
    assert report.endswith(SUMMARY_HINT)
