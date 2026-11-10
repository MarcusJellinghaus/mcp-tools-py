"""Budget tests for the mypy report."""

from mcp_tools_py.code_checker_mypy.models import MypyMessage, MypyResult
from mcp_tools_py.code_checker_mypy.reporting import (
    create_mypy_prompt,
    format_hint_lines,
)
from mcp_tools_py.utils.report_budget import (
    HINT_LINES,
    LOCATION_HINT,
    SUMMARY_HINT,
    TOOL_LINES,
)

HINT = "\n".join(f"hint {i}" for i in range(8))


def _msg(
    file: str,
    line: int,
    code: str | None,
    severity: str = "error",
    message: str = "problem",
    hint: str | None = None,
) -> MypyMessage:
    return MypyMessage(
        file=file,
        line=line,
        column=1,
        severity=severity,
        message=message,
        code=code,
        hint=hint,
    )


def _large_result() -> MypyResult:
    """30 codes x 100 errors with 8-line hints, plus 200 notes."""
    errors = [
        _msg(f"src/m{j}.py", j + 1, f"code{i:02d}", message=f"msg {j}", hint=HINT)
        for i in range(30)
        for j in range(100)
    ]
    notes = [
        _msg(
            f"src/n{j}.py",
            j + 1,
            "code00" if j % 2 else "loose",
            severity="note",
            message=f"note {j}",
        )
        for j in range(200)
    ]
    return MypyResult(return_code=1, messages=errors + notes)


def test_default_report_stays_within_budget() -> None:
    """The default call details 3 codes, summarises the rest and keeps the trailer."""
    prompt = create_mypy_prompt(_large_result())

    assert prompt is not None
    lines = prompt.splitlines()
    assert len(lines) < TOOL_LINES
    assert prompt.count("**code") == 3
    assert "**code00 (100 issues)" in prompt
    assert "**code02 (100 issues)" in prompt
    assert "**code03" not in prompt
    assert SUMMARY_HINT in prompt
    assert LOCATION_HINT in prompt
    assert lines[-5] == "To fix these issues:"
    assert f"    hint {HINT_LINES - 1}" in prompt
    assert f"    hint {HINT_LINES}" not in prompt
    assert f"... and {8 - HINT_LINES} more hint lines" in prompt


def test_format_hint_lines_caps_at_hint_lines() -> None:
    """Only the first HINT_LINES lines are kept, then a count line."""
    assert format_hint_lines(HINT) == [
        *(f"    hint {i}" for i in range(HINT_LINES)),
        f"    ... and {8 - HINT_LINES} more hint lines",
    ]
    assert format_hint_lines("a\nb") == ["    a", "    b"]
    assert format_hint_lines(None) == []


def test_note_joins_detailed_group_or_notes_section() -> None:
    """A note whose code is detailed sits in that group; others go to Notes."""
    result = MypyResult(
        return_code=1,
        messages=[
            _msg("src/a.py", 1, "arg-type"),
            _msg("src/a.py", 2, "arg-type", severity="note", message="in group"),
            _msg("src/b.py", 3, "misc", severity="note", message="elsewhere"),
        ],
    )
    prompt = create_mypy_prompt(result)

    assert prompt is not None
    group_at = prompt.index("**arg-type")
    notes_at = prompt.index("Notes (1)")
    assert group_at < prompt.index("- src/a.py: 2 — note: in group") < notes_at
    assert prompt.index("- src/b.py: 3 — elsewhere") > notes_at
    assert "**misc" not in prompt


def test_counts_only_lists_every_code() -> None:
    """max_issues=0 shows no locations and every code, uncapped."""
    prompt = create_mypy_prompt(_large_result(), max_issues=0)

    assert prompt is not None
    assert ".py" not in prompt
    assert "**" not in prompt
    assert "Notes" not in prompt
    for i in range(30):
        assert f"- code{i:02d}: 100 occurrences (src: 100)" in prompt
    assert SUMMARY_HINT not in prompt
