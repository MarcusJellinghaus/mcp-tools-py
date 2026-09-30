"""Unit tests for pylint parsers module."""

import json
from typing import Any

from mcp_tools_py.code_checker_pylint.parsers import parse_pylint_json_output


def _valid_item(**overrides: Any) -> dict[str, Any]:
    """Build a valid pylint JSON entry, with optional field overrides."""
    item: dict[str, Any] = {
        "type": "error",
        "module": "test_module",
        "obj": "",
        "line": 1,
        "column": 1,
        "path": "test.py",
        "symbol": "test",
        "message": "Test message",
        "message-id": "E0001",
    }
    item.update(overrides)
    return item


class TestParsePylintJsonOutput:
    """Test cases for parse_pylint_json_output function."""

    def test_parse_valid_json_output(self) -> None:
        """Test parsing valid JSON output from pylint."""
        json_data = [
            {
                "type": "error",
                "module": "test_module",
                "obj": "test_function",
                "line": 10,
                "column": 5,
                "path": "/path/to/file.py",
                "symbol": "undefined-variable",
                "message": "Undefined variable 'x'",
                "message-id": "E0602",
            },
            {
                "type": "warning",
                "module": "test_module",
                "obj": "test_function2",
                "line": 20,
                "column": 10,
                "path": "/path/to/file.py",
                "symbol": "unused-variable",
                "message": "Unused variable 'y'",
                "message-id": "W0612",
            },
        ]
        raw_output = json.dumps(json_data)

        messages, error = parse_pylint_json_output(raw_output)

        assert error is None
        assert len(messages) == 2

        # Check first message
        assert messages[0].type == "error"
        assert messages[0].module == "test_module"
        assert messages[0].obj == "test_function"
        assert messages[0].line == 10
        assert messages[0].column == 5
        assert messages[0].path == "/path/to/file.py"
        assert messages[0].symbol == "undefined-variable"
        assert messages[0].message == "Undefined variable 'x'"
        assert messages[0].message_id == "E0602"

        # Check second message
        assert messages[1].type == "warning"
        assert messages[1].message_id == "W0612"

    def test_parse_empty_output(self) -> None:
        """Test parsing empty output."""
        messages, error = parse_pylint_json_output("")

        assert error is None
        assert messages == []

    def test_parse_whitespace_only_output(self) -> None:
        """Test parsing whitespace-only output."""
        messages, error = parse_pylint_json_output("   \n  \t  ")

        assert error is None
        assert messages == []

    def test_parse_empty_json_array(self) -> None:
        """Test parsing empty JSON array."""
        messages, error = parse_pylint_json_output("[]")

        assert error is None
        assert messages == []

    def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON."""
        raw_output = "This is not valid JSON"

        messages, error = parse_pylint_json_output(raw_output)

        assert messages == []
        assert error is not None
        assert "Failed to parse Pylint JSON output" in error
        assert "This is not valid JSON" in error

    def test_parse_json_object_instead_of_array(self) -> None:
        """Test parsing JSON object instead of expected array."""
        raw_output = json.dumps({"type": "error", "message": "test"})

        messages, error = parse_pylint_json_output(raw_output)

        assert messages == []
        assert error is not None
        assert "Expected JSON array from pylint, got dict" in error

    def test_parse_json_with_non_dict_items(self) -> None:
        """Test parsing JSON array with non-dict items."""
        json_data = [
            {
                "type": "error",
                "module": "test_module",
                "obj": "",
                "line": 1,
                "column": 1,
                "path": "test.py",
                "symbol": "test",
                "message": "Test message",
                "message-id": "E0001",
            },
            "This is a string, not a dict",
            42,
            {
                "type": "warning",
                "module": "test_module2",
                "obj": "",
                "line": 2,
                "column": 1,
                "path": "test2.py",
                "symbol": "test2",
                "message": "Test message 2",
                "message-id": "W0001",
            },
        ]
        raw_output = json.dumps(json_data)

        messages, error = parse_pylint_json_output(raw_output)

        assert messages == []
        assert error is not None
        assert "entries that are not objects" in error
        assert "extra_args" in error

    def test_parse_json_with_missing_fields(self) -> None:
        """Test parsing JSON with missing required fields is an error."""
        json_data = [
            {
                "type": "warning",
                "module": "test_module",
                "line": 10,
                "column": 0,
                # Missing path, symbol and message-id
            },
        ]
        raw_output = json.dumps(json_data)

        messages, error = parse_pylint_json_output(raw_output)

        assert messages == []
        assert error is not None
        assert "entries without path, symbol or message-id" in error
        assert "keys: type, module, line, column" in error

    def test_non_dict_first_entry_is_error(self) -> None:
        """A non-dict first entry is reported, not a crash."""
        raw_output = json.dumps(["x", _valid_item()])

        messages, error = parse_pylint_json_output(raw_output)

        assert messages == []
        assert error is not None
        assert "entries that are not objects" in error
        assert "keys: str" in error

    def test_non_int_line_is_error(self) -> None:
        """A line that is not an int is an error."""
        raw_output = json.dumps([_valid_item(line="1")])

        messages, error = parse_pylint_json_output(raw_output)

        assert messages == []
        assert error is not None
        assert "entries without locations" in error

    def test_bool_column_is_error(self) -> None:
        """A bool column is not accepted as an int."""
        raw_output = json.dumps([_valid_item(column=True)])

        messages, error = parse_pylint_json_output(raw_output)

        assert messages == []
        assert error is not None
        assert "entries without locations" in error

    def test_command_line_entry_parses(self) -> None:
        """Pylint's 'Command line' entries are valid messages."""
        raw_output = json.dumps(
            [_valid_item(path="Command line", line=1, column=0, module="")]
        )

        messages, error = parse_pylint_json_output(raw_output)

        assert error is None
        assert len(messages) == 1
        assert messages[0].path == "Command line"
        assert messages[0].line == 1
        assert messages[0].column == 0

    def test_parse_very_long_output(self) -> None:
        """Test parsing very long output (error message truncation)."""
        raw_output = "x" * 300  # Invalid JSON, longer than 200 chars

        messages, error = parse_pylint_json_output(raw_output)

        assert messages == []
        assert error is not None
        assert "Failed to parse Pylint JSON output" in error
        assert "First 200 chars of output:" in error
        assert "xxx..." in error  # Should be truncated
