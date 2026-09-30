"""Unit tests for ruff parsers module."""

import json
import os

from mcp_tools_py.utils.ruff_parsing import parse_ruff_json_output


def _make_ruff_item(
    code: str = "D100",
    message: str = "Missing docstring in public module",
    filename: str = "/project/src/file.py",
    row: int = 1,
    column: int = 0,
    end_row: int = 1,
    end_column: int = 0,
    url: str = "https://docs.astral.sh/ruff/rules/undocumented-public-module",
    fix: object = None,
    noqa_row: int = 1,
) -> dict[str, object]:
    """Build a ruff JSON item dict."""
    item: dict[str, object] = {
        "code": code,
        "message": message,
        "filename": filename,
        "location": {"row": row, "column": column},
        "end_location": {"row": end_row, "column": end_column},
        "noqa_row": noqa_row,
        "url": url,
    }
    if fix is not None:
        item["fix"] = fix
    return item


class TestParseRuffJsonOutput:
    """Test cases for parse_ruff_json_output function."""

    def test_parse_valid_json_output(self) -> None:
        """Test parsing valid JSON output with two violations."""
        project_dir = "/project"
        json_data = [
            _make_ruff_item(
                code="D100",
                message="Missing docstring in public module",
                filename="/project/src/file.py",
                row=1,
                column=0,
                end_row=1,
                end_column=0,
                url="https://docs.astral.sh/ruff/rules/undocumented-public-module",
                fix={"applicability": "safe", "message": "Add docstring", "edits": []},
                noqa_row=1,
            ),
            _make_ruff_item(
                code="E501",
                message="Line too long (120 > 88)",
                filename="/project/src/other.py",
                row=10,
                column=89,
                end_row=10,
                end_column=120,
                url="https://docs.astral.sh/ruff/rules/line-too-long",
                noqa_row=10,
            ),
        ]
        raw_output = json.dumps(json_data)

        messages, error = parse_ruff_json_output(raw_output, project_dir)

        assert error is None
        assert len(messages) == 2

        assert messages[0].code == "D100"
        assert messages[0].message == "Missing docstring in public module"
        assert messages[0].filename == os.path.relpath(
            "/project/src/file.py", project_dir
        )
        assert messages[0].line == 1
        assert messages[0].column == 0
        assert messages[0].end_line == 1
        assert messages[0].end_column == 0
        assert (
            messages[0].url
            == "https://docs.astral.sh/ruff/rules/undocumented-public-module"
        )
        assert messages[0].fixable is True
        assert messages[0].noqa_row == 1

        assert messages[1].code == "E501"
        assert messages[1].fixable is False
        assert messages[1].noqa_row == 10

    def test_parse_empty_output(self) -> None:
        """Test parsing empty string."""
        messages, error = parse_ruff_json_output("", "/project")

        assert error is None
        assert messages == []

    def test_parse_whitespace_only_output(self) -> None:
        """Test parsing whitespace-only output."""
        messages, error = parse_ruff_json_output("   \n  \t  ", "/project")

        assert error is None
        assert messages == []

    def test_parse_empty_json_array(self) -> None:
        """Test parsing empty JSON array."""
        messages, error = parse_ruff_json_output("[]", "/project")

        assert error is None
        assert messages == []

    def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON."""
        messages, error = parse_ruff_json_output("This is not valid JSON", "/project")

        assert messages == []
        assert error is not None
        assert "Failed to parse ruff JSON output" in error
        assert "This is not valid JSON" in error

    def test_parse_json_object_instead_of_array(self) -> None:
        """Test parsing JSON object instead of expected array."""
        raw_output = json.dumps({"code": "D100", "message": "test"})

        messages, error = parse_ruff_json_output(raw_output, "/project")

        assert messages == []
        assert error is not None
        assert "Expected JSON array from ruff, got dict" in error

    def test_parse_absolute_paths_normalized(self) -> None:
        """Test that absolute paths are normalized to relative."""
        project_dir = "/project"
        json_data = [
            _make_ruff_item(filename="/project/src/deep/module.py"),
        ]
        raw_output = json.dumps(json_data)

        messages, error = parse_ruff_json_output(raw_output, project_dir)

        assert error is None
        assert len(messages) == 1
        expected = os.path.relpath("/project/src/deep/module.py", project_dir)
        assert messages[0].filename == expected

    def test_parse_fixable_detection(self) -> None:
        """Test fixable detection: with fix key -> True, without -> False."""
        project_dir = "/project"
        json_data = [
            _make_ruff_item(
                code="D100",
                fix={"applicability": "safe", "message": "Add docstring", "edits": []},
            ),
            _make_ruff_item(code="E501"),
        ]
        raw_output = json.dumps(json_data)

        messages, error = parse_ruff_json_output(raw_output, project_dir)

        assert error is None
        assert len(messages) == 2
        assert messages[0].fixable is True
        assert messages[1].fixable is False

    def test_parse_missing_optional_fields(self) -> None:
        """Test that an item without location and filename is an error."""
        json_data = [{"code": "X001", "message": "test"}]

        messages, error = parse_ruff_json_output(json.dumps(json_data), "/project")

        assert messages == []
        assert error is not None
        assert "without locations" in error

    def test_statistics_output_is_error(self) -> None:
        """Test that ruff --statistics JSON is rejected, not turned into violations."""
        json_data = [
            {
                "code": "D100",
                "name": "undocumented-public-module",
                "count": 3,
                "fixable": False,
                "fixable_count": 0,
            }
        ]

        messages, error = parse_ruff_json_output(json.dumps(json_data), "/project")

        assert messages == []
        assert error is not None
        assert "without locations" in error
        assert "code, name, count, fixable, fixable_count" in error
        assert "extra_args" not in error

    def test_non_dict_entry_is_error(self) -> None:
        """Test that a non-object entry fails the whole parse."""
        raw_output = json.dumps([_make_ruff_item(), 42])

        messages, error = parse_ruff_json_output(raw_output, "/project")

        assert messages == []
        assert error is not None
        assert "entries that are not objects" in error
        assert "int" in error

    def test_missing_location_row_is_error(self) -> None:
        """Test that an entry without location.row is an error."""
        item = _make_ruff_item()
        item["location"] = {"column": 0}

        messages, error = parse_ruff_json_output(json.dumps([item]), "/project")

        assert messages == []
        assert error is not None
        assert "without locations" in error

    def test_non_int_column_is_error(self) -> None:
        """Test that a non-int location.column (including bool) is an error."""
        for column in ("3", True, None):
            item = _make_ruff_item()
            item["location"] = {"row": 1, "column": column}

            messages, error = parse_ruff_json_output(json.dumps([item]), "/project")

            assert messages == []
            assert error is not None
            assert "without locations" in error

    def test_missing_message_is_error(self) -> None:
        """Test that an entry without message is an error."""
        item = _make_ruff_item()
        del item["message"]

        messages, error = parse_ruff_json_output(json.dumps([item]), "/project")

        assert messages == []
        assert error is not None
        assert "without code, message or filename" in error

    def test_missing_filename_is_error(self) -> None:
        """Test that an entry with null filename is an error."""
        item = _make_ruff_item()
        item["filename"] = None

        messages, error = parse_ruff_json_output(json.dumps([item]), "/project")

        assert messages == []
        assert error is not None
        assert "without code, message or filename" in error

    def test_invalid_syntax_entry_with_nulls_parses(self) -> None:
        """Test that null optional fields (as in invalid-syntax entries) are accepted."""
        item = _make_ruff_item(code="invalid-syntax")
        item["url"] = None
        item["noqa_row"] = None
        item["fix"] = None
        item["cell"] = None

        messages, error = parse_ruff_json_output(json.dumps([item]), "/project")

        assert error is None
        assert len(messages) == 1
        assert messages[0].code == "invalid-syntax"
        assert messages[0].url == ""
        assert messages[0].noqa_row == -1
        assert messages[0].fixable is False

    def test_null_code_normalised(self) -> None:
        """Test that code: null is normalised to invalid-syntax."""
        item = _make_ruff_item()
        item["code"] = None

        messages, error = parse_ruff_json_output(json.dumps([item]), "/project")

        assert error is None
        assert len(messages) == 1
        assert messages[0].code == "invalid-syntax"

    def test_parse_very_long_output(self) -> None:
        """Test parsing very long invalid output (error message truncation)."""
        raw_output = "x" * 300

        messages, error = parse_ruff_json_output(raw_output, "/project")

        assert messages == []
        assert error is not None
        assert "Failed to parse ruff JSON output" in error
        assert "First 200 chars of output:" in error
        assert "xxx..." in error
