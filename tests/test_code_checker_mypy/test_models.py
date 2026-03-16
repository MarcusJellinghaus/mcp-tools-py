"""Test mypy models functionality."""

import pytest

from mcp_tools_py.code_checker_mypy.models import (
    MypyMessage,
    MypyResult,
    MypySeverity,
)


def test_mypy_severity_enum() -> None:
    """Test MypySeverity enum values."""
    assert MypySeverity.ERROR.value == "error"
    assert MypySeverity.WARNING.value == "warning"
    assert MypySeverity.NOTE.value == "note"


def test_mypy_message_creation() -> None:
    """Test creating MypyMessage instances."""
    msg = MypyMessage(
        file="test.py",
        line=10,
        column=5,
        severity="error",
        message="Type error found",
        code="type-error",
    )

    assert msg.file == "test.py"
    assert msg.line == 10
    assert msg.column == 5
    assert msg.severity == "error"
    assert msg.message == "Type error found"
    assert msg.code == "type-error"


def test_mypy_message_optional_code() -> None:
    """Test MypyMessage with optional code field."""
    msg = MypyMessage(
        file="test.py", line=10, column=5, severity="note", message="See above"
    )

    assert msg.code is None


def test_mypy_result_creation() -> None:
    """Test creating MypyResult instances."""
    messages = [
        MypyMessage(
            file="test.py",
            line=10,
            column=5,
            severity="error",
            message="Error 1",
            code="err1",
        ),
        MypyMessage(
            file="test.py",
            line=20,
            column=10,
            severity="warning",
            message="Warning 1",
            code="warn1",
        ),
    ]

    result = MypyResult(
        return_code=1,
        messages=messages,
        error=None,
        raw_output="raw output text",
        files_checked=5,
        errors_found=1,
    )

    assert result.return_code == 1
    assert len(result.messages) == 2
    assert result.error is None
    assert result.raw_output == "raw output text"
    assert result.files_checked == 5
    assert result.errors_found == 1


def test_mypy_result_get_error_codes() -> None:
    """Test MypyResult.get_error_codes method."""
    messages = [
        MypyMessage(
            file="a.py", line=1, column=1, severity="error", message="E1", code="err1"
        ),
        MypyMessage(
            file="b.py", line=2, column=2, severity="error", message="E2", code="err2"
        ),
        MypyMessage(
            file="c.py", line=3, column=3, severity="error", message="E3", code="err1"
        ),  # Duplicate
        MypyMessage(
            file="d.py", line=4, column=4, severity="note", message="N1", code=None
        ),  # No code
    ]

    result = MypyResult(return_code=1, messages=messages)
    codes = result.get_error_codes()

    assert codes == {"err1", "err2"}


def test_mypy_result_get_messages_by_severity() -> None:
    """Test MypyResult.get_messages_by_severity method."""
    messages = [
        MypyMessage(
            file="a.py", line=1, column=1, severity="error", message="E1", code="err1"
        ),
        MypyMessage(
            file="b.py",
            line=2,
            column=2,
            severity="warning",
            message="W1",
            code="warn1",
        ),
        MypyMessage(
            file="c.py", line=3, column=3, severity="error", message="E2", code="err2"
        ),
        MypyMessage(
            file="d.py", line=4, column=4, severity="note", message="N1", code=None
        ),
        MypyMessage(
            file="e.py",
            line=5,
            column=5,
            severity="warning",
            message="W2",
            code="warn2",
        ),
    ]

    result = MypyResult(return_code=1, messages=messages)

    errors = result.get_messages_by_severity("error")
    assert len(errors) == 2
    assert all(msg.severity == "error" for msg in errors)
    assert errors[0].message == "E1"
    assert errors[1].message == "E2"

    warnings = result.get_messages_by_severity("warning")
    assert len(warnings) == 2
    assert all(msg.severity == "warning" for msg in warnings)

    notes = result.get_messages_by_severity("note")
    assert len(notes) == 1
    assert notes[0].message == "N1"

    # Test non-existent severity
    infos = result.get_messages_by_severity("info")
    assert len(infos) == 0


def test_mypy_result_empty() -> None:
    """Test MypyResult with no messages."""
    result = MypyResult(return_code=0, messages=[])

    assert result.return_code == 0
    assert len(result.messages) == 0
    assert result.get_error_codes() == set()
    assert result.get_messages_by_severity("error") == []
