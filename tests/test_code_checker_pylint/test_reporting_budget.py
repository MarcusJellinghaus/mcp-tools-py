"""Budget tests for the pylint report."""

import sys
from unittest.mock import patch

from mcp_tools_py.code_checker_pylint.models import PylintMessage, PylintResult
from mcp_tools_py.code_checker_pylint.reporting import get_pylint_prompt
from mcp_tools_py.utils.report_budget import DETAIL_HINT, SUMMARY_HINT, TOOL_LINES

_PATCH = "mcp_tools_py.code_checker_pylint.reporting.get_pylint_results"


def _msg(message_id: str, msg_type: str, line: int, path: str) -> PylintMessage:
    return PylintMessage(
        type=msg_type,
        module="mod",
        obj="obj",
        line=line,
        column=0,
        path=path,
        symbol=f"sym-{message_id}",
        message=f"problem {message_id}",
        message_id=message_id,
    )


def _prompt(messages: list[PylintMessage], max_issues: int = 1) -> str:
    with patch(_PATCH, return_value=PylintResult(return_code=4, messages=messages)):
        prompt = get_pylint_prompt(
            "/project", python_executable=sys.executable, max_issues=max_issues
        )
    assert prompt is not None
    return prompt


def test_large_result_stays_within_budget() -> None:
    """1 rule x 500 hits in 60 files plus 40 rules: bounded, no JSON, hint last."""
    messages = [
        _msg("E0602", "error", i, f"/project/src/f{i % 60}.py") for i in range(500)
    ]
    for r in range(40):
        messages += [
            _msg(f"C{r:04d}", "convention", n, "/project/src/x.py")
            for n in range(r + 1)
        ]
    prompt = _prompt(messages)
    lines = prompt.splitlines()
    assert len(lines) < TOOL_LINES
    assert "{" not in prompt
    assert '"module"' not in prompt
    assert lines[-1] == SUMMARY_HINT
    assert "pylint found 500 issues with rule E0602 sym-E0602 (src: 500)." in prompt
    assert "... and 410 more locations in 50 more rows" in prompt


def test_few_remaining_rules_end_with_detail_hint() -> None:
    """5 rules with max_issues=1: the report ends with DETAIL_HINT."""
    messages = [_msg(f"W{r:04d}", "warning", 1, "/project/src/a.py") for r in range(5)]
    prompt = _prompt(messages)
    assert prompt.splitlines()[-1] == DETAIL_HINT
    assert "--- 4 additional rules found (4 occurrences) ---" in prompt
