"""Test mypy parser functionality."""

import pytest

from mcp_tools_py.code_checker_mypy.models import MypyMessage
from mcp_tools_py.code_checker_mypy.parsers import parse_mypy_json_output


def test_parse_mypy_json_output_valid() -> None:
    """Test parsing valid mypy JSON output."""
    json_output = """{"file": "test.py", "line": 10, "column": 5, "severity": "error", "message": "Missing return statement", "code": "return"}
{"file": "test.py", "line": 20, "column": 10, "severity": "warning", "message": "Unused variable", "code": "unused-var"}"""

    messages, error = parse_mypy_json_output(json_output)

    assert error is None
    assert len(messages) == 2

    # Check first message
    assert messages[0].file == "test.py"
    assert messages[0].line == 10
    assert messages[0].column == 5
    assert messages[0].severity == "error"
    assert messages[0].message == "Missing return statement"
    assert messages[0].code == "return"

    # Check second message
    assert messages[1].severity == "warning"
    assert messages[1].message == "Unused variable"


def test_parse_mypy_json_output_with_empty_lines() -> None:
    """Test parsing mypy output with empty lines."""
    json_output = """
{"file": "test.py", "line": 10, "column": 5, "severity": "error", "message": "Type error", "code": "type"}

{"file": "test2.py", "line": 5, "column": 3, "severity": "note", "message": "See above", "code": null}
"""

    messages, error = parse_mypy_json_output(json_output)

    assert error is None
    assert len(messages) == 2
    assert messages[0].file == "test.py"
    assert messages[1].file == "test2.py"
    assert messages[1].code is None


def test_parse_mypy_json_output_mixed_content() -> None:
    """Test parsing mypy output with mixed JSON and non-JSON lines."""
    json_output = """Success: no issues found in 1 source file
{"file": "test.py", "line": 10, "column": 5, "severity": "error", "message": "Error found", "code": "error"}
Found 1 error in 1 file (checked 1 source file)"""

    messages, error = parse_mypy_json_output(json_output)

    assert error is None
    assert len(messages) == 1
    assert messages[0].message == "Error found"


def test_parse_mypy_json_output_invalid_json() -> None:
    """Test parsing completely invalid JSON."""
    json_output = """This is not JSON at all
Neither is this
And definitely not this"""

    messages, error = parse_mypy_json_output(json_output)

    assert len(messages) == 0
    # Error should be None since we're just ignoring non-JSON lines
    assert error is None


def test_parse_mypy_json_output_malformed_json_object() -> None:
    """Test parsing malformed JSON objects."""
    json_output = """{"incomplete": "json"
{"file": "test.py", "line": 10}"""

    messages, _ = parse_mypy_json_output(json_output)

    # Should parse the second valid JSON even if first is incomplete
    assert len(messages) == 1
    assert messages[0].file == "test.py"
    assert messages[0].line == 10
    assert messages[0].column == 0  # Default value
    assert messages[0].message == ""  # Default value


def test_parse_mypy_json_output_empty() -> None:
    """Test parsing empty output."""
    messages, error = parse_mypy_json_output("")

    assert len(messages) == 0
    assert error is None
