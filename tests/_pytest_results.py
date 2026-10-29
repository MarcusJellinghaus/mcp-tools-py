"""Test helper for hand-built check_code_with_pytest results."""

from typing import Any

from mcp_tools_py.code_checker_pytest.verdict import RunStatus, RunVerdict


def make_pytest_results(
    status: RunStatus = RunStatus.PASSED,
    problems: list[str] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Hand-built check_code_with_pytest result; summary_text defaults to ''."""
    return {
        "verdict": RunVerdict(status, problems or [], 0),
        "summary_text": "",
        **fields,
    }
