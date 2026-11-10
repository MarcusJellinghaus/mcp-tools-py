"""Budget tests for the lint-imports report."""

from mcp_tools_py.code_checker_lint_imports.runners import (
    _CONTRACT_HINT,
    _format_report,
)
from mcp_tools_py.utils.report_budget import TOOL_LINES

_INFO = "[Info: stripped --verbose/-v from extra_args]"


def test_large_broken_report_is_bounded_and_keeps_header() -> None:
    body = "\n".join(f"mypkg.mod{i} -> mypkg.other{i} (l.{i})" for i in range(2000))
    result = _format_report(
        state="BROKEN",
        summary=(1, 1),
        broken_contracts=["Layers"],
        warnings=[],
        raw_body=body,
        info_lines=[_INFO],
    )
    lines = result.splitlines()
    assert len(lines) <= TOOL_LINES
    non_info = [line for line in lines if line.strip() and not line.startswith("[Info")]
    assert non_info[0].startswith("=== BROKEN: ")
    assert "lines /" in result and "omitted ...]" in result
    assert lines[-1] == _CONTRACT_HINT


def test_short_report_is_unchanged_and_has_no_hint() -> None:
    result = _format_report(
        state="PASSED",
        summary=(3, 0),
        broken_contracts=[],
        warnings=[],
        raw_body="Contracts: 3 kept, 0 broken.",
        info_lines=[],
    )
    assert result == (
        "=== PASSED ===\n"
        "Contracts: 3 kept, 0 broken\n"
        "\n"
        "Contracts: 3 kept, 0 broken."
    )
    assert _CONTRACT_HINT not in result
