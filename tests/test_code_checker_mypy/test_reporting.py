"""Test mypy reporting functionality."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_tools_py.code_checker_mypy.models import MypyMessage, MypyResult
from mcp_tools_py.code_checker_mypy.reporting import create_mypy_prompt, get_mypy_prompt
from tests.conftest import make_command_result

HEADER = "Mypy found type issues that need attention:"


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


def _mixed_result() -> MypyResult:
    """Three codes: arg-type x3 (src 2, tests 1), attr-defined x1, misc x1."""
    return MypyResult(
        return_code=1,
        messages=[
            _msg("tests/t.py", 3, "misc"),
            _msg("src/a.py", 1, "arg-type"),
            _msg("src/b.py", 2, "arg-type"),
            _msg("tests/t.py", 4, "arg-type"),
            _msg("src/a.py", 5, "attr-defined"),
        ],
    )


def test_create_mypy_prompt_no_messages() -> None:
    """Test prompt creation with no messages."""
    result = MypyResult(return_code=0, messages=[])
    prompt = create_mypy_prompt(result)

    assert prompt is None


def test_create_mypy_prompt_with_messages() -> None:
    """Default output: header, total line, every code detailed, footer."""
    prompt = create_mypy_prompt(_mixed_result())

    assert prompt is not None
    lines = prompt.splitlines()
    assert lines[0] == HEADER
    assert lines[2] == "mypy found 5 issues across 3 rules"
    assert "**Summary:**" not in prompt

    # Ordered by count descending, ties alphabetical
    arg = prompt.index("**arg-type (3 issues) (src: 2, tests: 1)**")
    attr = prompt.index("**attr-defined (1 issue) (src: 1)**")
    misc = prompt.index("**misc (1 issue) (tests: 1)**")
    assert arg < attr < misc

    assert "- src/a.py:1:1 - problem" in prompt
    assert "To fix these issues:" in prompt


def test_create_mypy_prompt_code_none_grouped_as_other() -> None:
    """Messages without a code are grouped under ``other``."""
    result = MypyResult(return_code=1, messages=[_msg("main.py", 15, None)])
    prompt = create_mypy_prompt(result)

    assert prompt is not None
    assert "**other (1 issue) ((root): 1)**" in prompt


def test_create_mypy_prompt_many_messages_same_code() -> None:
    """Only the first five locations of a code are listed."""
    messages = [_msg(f"src/file{i}.py", i * 10, "type-error") for i in range(10)]

    result = MypyResult(return_code=1, messages=messages)
    prompt = create_mypy_prompt(result)

    assert prompt is not None
    assert "**type-error (10 issues) (src: 10)**" in prompt
    assert "src/file0.py:0:1" in prompt
    assert "src/file4.py:40:1" in prompt
    assert "src/file5.py:50:1" not in prompt
    assert "... and 5 more" in prompt


def test_create_mypy_prompt_max_issues_one() -> None:
    """The top code is detailed; the rest get one summary line each."""
    prompt = create_mypy_prompt(_mixed_result(), max_issues=1)

    assert prompt is not None
    assert "**arg-type (3 issues) (src: 2, tests: 1)**" in prompt
    assert "**attr-defined" not in prompt
    assert "- attr-defined: 1 occurrence (src: 1)" in prompt
    assert "- misc: 1 occurrence (tests: 1)" in prompt
    assert "tests/t.py:3:1" not in prompt


@pytest.mark.parametrize("max_issues", [0, -3])
def test_create_mypy_prompt_counts_only(max_issues: int) -> None:
    """max_issues <= 0 shows the total line and summary lines only."""
    result = _mixed_result()
    notes = [_msg("src/a.py", 9, None, severity="note", message="Revealed")]
    result = result._replace(messages=result.messages + notes)

    prompt = create_mypy_prompt(result, max_issues=max_issues)

    assert prompt is not None
    assert "mypy found 5 issues across 3 rules" in prompt
    assert "- arg-type: 3 occurrences (src: 2, tests: 1)" in prompt
    assert "- attr-defined: 1 occurrence (src: 1)" in prompt
    assert "- misc: 1 occurrence (tests: 1)" in prompt
    assert "**" not in prompt
    assert ".py:" not in prompt
    assert "Notes:" not in prompt


def test_create_mypy_prompt_hint_lines_indented() -> None:
    """Hint lines appear indented under their error."""
    result = MypyResult(
        return_code=1,
        messages=[_msg("src/a.py", 1, "arg-type", hint="hint one\nhint two")],
    )
    prompt = create_mypy_prompt(result)

    assert prompt is not None
    assert "- src/a.py:1:1 - problem\n    hint one\n    hint two" in prompt


def test_create_mypy_prompt_notes_section_at_end() -> None:
    """Standalone notes go in one Notes section and are not counted."""
    result = MypyResult(
        return_code=1,
        messages=[
            _msg("src/a.py", 9, None, severity="note", message="Revealed A"),
            _msg("src/a.py", 1, "arg-type"),
            _msg("src/b.py", 2, None, severity="note", message="Revealed B"),
        ],
    )
    prompt = create_mypy_prompt(result)

    assert prompt is not None
    assert "mypy found 1 issue across 1 rule" in prompt
    notes_at = prompt.index("Notes:")
    assert prompt.index("**arg-type") < notes_at
    assert prompt.index("- src/a.py:9:1 - Revealed A") > notes_at
    assert prompt.index("- src/b.py:2:1 - Revealed B") > notes_at
    assert notes_at < prompt.index("To fix these issues:")
    assert "other" not in prompt


def test_create_mypy_prompt_notes_only() -> None:
    """A notes-only run has no header and no footer."""
    result = MypyResult(
        return_code=0,
        messages=[
            _msg(
                "src/a.py",
                9,
                None,
                severity="note",
                message='Revealed type is "builtins.int"',
            )
        ],
    )

    assert create_mypy_prompt(result) == (
        "mypy found 0 issues across 0 rules\n"
        "\n"
        "Notes:\n"
        '- src/a.py:9:1 - Revealed type is "builtins.int"'
    )
    assert create_mypy_prompt(result, max_issues=0) == (
        "mypy found 0 issues across 0 rules"
    )


def test_create_mypy_prompt_singular_total() -> None:
    """One issue in one rule uses singular words."""
    result = MypyResult(return_code=1, messages=[_msg("src/a.py", 1, "misc")])
    prompt = create_mypy_prompt(result)

    assert prompt is not None
    assert "mypy found 1 issue across 1 rule\n" in prompt


def test_create_mypy_prompt_execution_error() -> None:
    """Test prompt creation when there's an execution error."""
    # Test with an empty result (no messages)
    result = MypyResult(return_code=1, messages=[])
    prompt = create_mypy_prompt(result)
    assert prompt is None  # No messages means no prompt


def test_create_mypy_prompt_summary_statistics() -> None:
    """Warnings count as issues; the old Summary block is gone."""
    result = MypyResult(
        return_code=1,
        messages=[
            _msg("app.py", 10, "type"),
            _msg("app.py", 20, "type"),
            _msg("utils.py", 30, "import", severity="warning"),
        ],
    )
    prompt = create_mypy_prompt(result)

    assert prompt is not None
    assert "mypy found 3 issues across 2 rules" in prompt
    assert "**Summary:**" not in prompt
    assert "Notes:" not in prompt
    assert "**type (2 issues) ((root): 2)**" in prompt
    assert "**import (1 issue) ((root): 1)**" in prompt


def test_mypy_result_methods() -> None:
    """Test MypyResult helper methods."""
    messages = [
        MypyMessage(
            file="test.py",
            line=10,
            column=5,
            severity="error",
            message="Error 1",
            code="type",
        ),
        MypyMessage(
            file="test.py",
            line=20,
            column=5,
            severity="warning",
            message="Warning 1",
            code="unused",
        ),
        MypyMessage(
            file="test.py",
            line=30,
            column=5,
            severity="error",
            message="Error 2",
            code="type",
        ),
        MypyMessage(
            file="test.py",
            line=40,
            column=5,
            severity="note",
            message="Note 1",
            code="misc",
        ),
    ]

    result = MypyResult(return_code=1, messages=messages)

    # Test get_error_codes
    codes = result.get_error_codes()
    assert codes == {"type", "unused", "misc"}

    # Test get_messages_by_severity
    errors = result.get_messages_by_severity("error")
    assert len(errors) == 2
    assert all(msg.severity == "error" for msg in errors)

    warnings = result.get_messages_by_severity("warning")
    assert len(warnings) == 1
    assert warnings[0].message == "Warning 1"

    notes = result.get_messages_by_severity("note")
    assert len(notes) == 1
    assert notes[0].message == "Note 1"


@pytest.mark.parametrize("follow_imports", [None, "silent"])
def test_get_mypy_prompt_forwards_follow_imports_unchanged(
    tmp_path: Path, follow_imports: str | None
) -> None:
    """get_mypy_prompt passes follow_imports down without coercing None."""
    with patch("mcp_tools_py.code_checker_mypy.runners.execute_command") as mock_exec:
        mock_exec.return_value = make_command_result()
        get_mypy_prompt(
            str(tmp_path),
            python_executable=sys.executable,
            target_directories=["."],
            follow_imports=follow_imports,
        )

    command = mock_exec.call_args.kwargs["command"]
    if follow_imports is None:
        assert "--follow-imports" not in command
    else:
        assert command[command.index("--follow-imports") + 1] == follow_imports


def test_get_mypy_prompt_forwards_max_issues(tmp_path: Path) -> None:
    """get_mypy_prompt passes max_issues to create_mypy_prompt."""
    with (
        patch("mcp_tools_py.code_checker_mypy.runners.run_mypy_check") as mock_run,
        patch(
            "mcp_tools_py.code_checker_mypy.reporting.create_mypy_prompt"
        ) as mock_create,
    ):
        mock_run.return_value = MypyResult(return_code=0, messages=[])
        get_mypy_prompt(str(tmp_path), python_executable=sys.executable, max_issues=2)

    assert mock_create.call_args.kwargs["max_issues"] == 2
