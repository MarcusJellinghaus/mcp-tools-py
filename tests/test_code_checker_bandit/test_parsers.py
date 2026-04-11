"""Unit tests for bandit parsers module."""

import json
import os

from mcp_tools_py.code_checker_bandit.parsers import parse_bandit_json_output


def _make_bandit_result_item(
    test_id: str = "B101",
    test_name: str = "assert_used",
    issue_severity: str = "LOW",
    issue_confidence: str = "HIGH",
    issue_text: str = "Use of assert detected.",
    filename: str = "/project/src/foo.py",
    line_number: int = 10,
    col_offset: int = 0,
    end_col_offset: int = 15,
    line_range: list[int] | None = None,
    more_info: str = "https://bandit.readthedocs.io/en/latest/plugins/b101_assert_used.html",
    issue_cwe: dict[str, object] | None = None,
    code: str = "9 \n10 assert x > 0\n11 \n",
) -> dict[str, object]:
    """Build a bandit JSON result item dict."""
    if line_range is None:
        line_range = [line_number]
    if issue_cwe is None:
        issue_cwe = {
            "id": 703,
            "link": "https://cwe.mitre.org/data/definitions/703.html",
        }
    return {
        "test_id": test_id,
        "test_name": test_name,
        "issue_severity": issue_severity,
        "issue_confidence": issue_confidence,
        "issue_text": issue_text,
        "filename": filename,
        "line_number": line_number,
        "col_offset": col_offset,
        "end_col_offset": end_col_offset,
        "line_range": line_range,
        "more_info": more_info,
        "issue_cwe": issue_cwe,
        "code": code,
    }


def _make_bandit_json(
    results: list[dict[str, object]] | None = None,
    errors: list[dict[str, str]] | None = None,
) -> str:
    """Build a complete bandit JSON output string."""
    data: dict[str, object] = {
        "errors": errors or [],
        "results": results or [],
        "metrics": {},
        "generated_at": "2024-01-01T00:00:00Z",
    }
    return json.dumps(data)


class TestParseBanditJsonOutput:
    """Test cases for parse_bandit_json_output function."""

    def test_parse_valid_json_with_results(self) -> None:
        """Test parsing valid JSON output with results."""
        project_dir = "/project"
        raw_output = _make_bandit_json(
            results=[
                _make_bandit_result_item(
                    test_id="B101",
                    test_name="assert_used",
                    issue_severity="LOW",
                    issue_confidence="HIGH",
                    issue_text="Use of assert detected.",
                    filename="/project/src/foo.py",
                    line_number=10,
                    more_info="https://bandit.readthedocs.io/en/latest/plugins/b101_assert_used.html",
                    issue_cwe={
                        "id": 703,
                        "link": "https://cwe.mitre.org/data/definitions/703.html",
                    },
                ),
            ]
        )

        messages, errors, parse_error = parse_bandit_json_output(
            raw_output, project_dir
        )

        assert parse_error is None
        assert errors == []
        assert len(messages) == 1

        msg = messages[0]
        assert msg.test_id == "B101"
        assert msg.test_name == "assert_used"
        assert msg.issue_severity == "LOW"
        assert msg.issue_confidence == "HIGH"
        assert msg.issue_text == "Use of assert detected."
        assert msg.filename == os.path.relpath("/project/src/foo.py", project_dir)
        assert msg.line_number == 10
        assert (
            msg.more_info
            == "https://bandit.readthedocs.io/en/latest/plugins/b101_assert_used.html"
        )
        assert msg.cwe_id == 703
        assert msg.cwe_link == "https://cwe.mitre.org/data/definitions/703.html"

    def test_parse_valid_json_with_errors(self) -> None:
        """Test parsing valid JSON with errors array."""
        raw_output = _make_bandit_json(
            errors=[
                {"filename": "bad.py", "reason": "syntax error"},
                {"filename": "worse.py", "reason": "encoding issue"},
            ]
        )

        messages, errors, parse_error = parse_bandit_json_output(raw_output, "/project")

        assert parse_error is None
        assert messages == []
        assert len(errors) == 2
        assert errors[0] == "bad.py: syntax error"
        assert errors[1] == "worse.py: encoding issue"

    def test_parse_empty_output(self) -> None:
        """Test parsing empty string."""
        messages, errors, parse_error = parse_bandit_json_output("", "/project")

        assert parse_error is None
        assert messages == []
        assert errors == []

    def test_parse_empty_results_array(self) -> None:
        """Test parsing valid JSON with empty results."""
        raw_output = _make_bandit_json(results=[], errors=[])

        messages, errors, parse_error = parse_bandit_json_output(raw_output, "/project")

        assert parse_error is None
        assert messages == []
        assert errors == []

    def test_parse_invalid_json(self) -> None:
        """Test parsing invalid JSON."""
        messages, errors, parse_error = parse_bandit_json_output(
            "This is not valid JSON", "/project"
        )

        assert messages == []
        assert errors == []
        assert parse_error is not None
        assert "Failed to parse bandit JSON output" in parse_error
        assert "This is not valid JSON" in parse_error

    def test_parse_array_instead_of_object(self) -> None:
        """Test parsing JSON array instead of expected object."""
        raw_output = json.dumps([{"test_id": "B101"}])

        messages, errors, parse_error = parse_bandit_json_output(raw_output, "/project")

        assert messages == []
        assert errors == []
        assert parse_error is not None
        assert "Expected JSON object from bandit, got list" in parse_error

    def test_parse_paths_normalized(self) -> None:
        """Test that absolute paths are normalized to relative."""
        project_dir = "/project"
        raw_output = _make_bandit_json(
            results=[
                _make_bandit_result_item(
                    filename="/project/src/deep/module.py",
                ),
            ]
        )

        messages, errors, parse_error = parse_bandit_json_output(
            raw_output, project_dir
        )

        assert parse_error is None
        assert len(messages) == 1
        expected = os.path.relpath("/project/src/deep/module.py", project_dir)
        assert messages[0].filename == expected

    def test_parse_missing_cwe_fields(self) -> None:
        """Test parsing result with missing issue_cwe."""
        raw_output = _make_bandit_json(
            results=[
                _make_bandit_result_item(issue_cwe=None),
            ]
        )
        # Override the issue_cwe to be missing entirely
        data = json.loads(raw_output)
        data["results"][0].pop("issue_cwe", None)
        raw_output = json.dumps(data)

        messages, errors, parse_error = parse_bandit_json_output(raw_output, "/project")

        assert parse_error is None
        assert len(messages) == 1
        assert messages[0].cwe_id == 0
        assert messages[0].cwe_link == ""

    def test_parse_very_long_invalid_output(self) -> None:
        """Test parsing very long invalid output (error message truncation)."""
        raw_output = "x" * 300

        messages, errors, parse_error = parse_bandit_json_output(raw_output, "/project")

        assert messages == []
        assert errors == []
        assert parse_error is not None
        assert "Failed to parse bandit JSON output" in parse_error
        assert "First 200 chars of output:" in parse_error
        assert "xxx..." in parse_error
