"""Unit tests for pylint reporting module."""

import sys
from unittest.mock import patch

from mcp_tools_py.code_checker_pylint.models import PylintMessage, PylintResult
from mcp_tools_py.code_checker_pylint.reporting import (
    MAX_LOCATIONS_PER_ISSUE,
    _group_and_sort_issues,
    get_direct_instruction_for_pylint_code,
    get_prompt_for_known_pylint_code,
    get_prompt_for_unknown_pylint_code,
    get_pylint_prompt,
)


def _make_message(
    message_id: str = "W0612",
    symbol: str = "unused-variable",
    msg_type: str = "warning",
    line: int = 1,
) -> PylintMessage:
    """Helper to create a PylintMessage with sensible defaults."""
    return PylintMessage(
        type=msg_type,
        module="test_module",
        obj="test_obj",
        line=line,
        column=0,
        path="test.py",
        symbol=symbol,
        message="test message",
        message_id=message_id,
    )


class TestGroupAndSortIssues:
    """Test cases for _group_and_sort_issues helper."""

    def test_empty_messages(self) -> None:
        """Empty list returns empty list."""
        result = _group_and_sort_issues([])
        assert result == []

    def test_single_issue_type(self) -> None:
        """One message_id returns a single group."""
        msgs = [_make_message("W0612", "unused-variable", "warning")]
        result = _group_and_sort_issues(msgs)
        assert len(result) == 1
        assert result[0].message_id == "W0612"
        assert result[0].symbol == "unused-variable"
        assert result[0].type == "warning"
        assert result[0].messages == msgs

    def test_severity_ordering(self) -> None:
        """Fatal before error before warning before refactor before convention."""
        msgs = [
            _make_message("C0411", "wrong-import-order", "convention"),
            _make_message("E0602", "undefined-variable", "error"),
            _make_message("F0001", "fatal-error", "fatal"),
            _make_message("W0612", "unused-variable", "warning"),
            _make_message("R0902", "too-many-instance-attributes", "refactor"),
        ]
        result = _group_and_sort_issues(msgs)
        types = [g.type for g in result]
        assert types == ["fatal", "error", "warning", "refactor", "convention"]

    def test_frequency_ordering_within_same_severity(self) -> None:
        """More occurrences first among same severity level."""
        msgs = [
            _make_message("W0612", "unused-variable", "warning", line=1),
            _make_message("W0613", "unused-argument", "warning", line=2),
            _make_message("W0613", "unused-argument", "warning", line=3),
            _make_message("W0613", "unused-argument", "warning", line=4),
        ]
        result = _group_and_sort_issues(msgs)
        assert len(result) == 2
        assert result[0].message_id == "W0613"  # 3 occurrences
        assert result[1].message_id == "W0612"  # 1 occurrence

    def test_severity_takes_precedence_over_frequency(self) -> None:
        """1 error sorts before 10 conventions."""
        msgs = [_make_message("E0602", "undefined-variable", "error")]
        msgs += [
            _make_message("C0411", "wrong-import-order", "convention", line=i)
            for i in range(10)
        ]
        result = _group_and_sort_issues(msgs)
        assert result[0].message_id == "E0602"
        assert result[1].message_id == "C0411"

    def test_group_contains_all_messages(self) -> None:
        """Each group has all messages for that message_id."""
        msgs = [
            _make_message("W0612", "unused-variable", "warning", line=1),
            _make_message("W0612", "unused-variable", "warning", line=2),
            _make_message("W0612", "unused-variable", "warning", line=3),
        ]
        result = _group_and_sort_issues(msgs)
        assert len(result) == 1
        assert len(result[0].messages) == 3
        assert set(m.line for m in result[0].messages) == {1, 2, 3}


class TestGetDirectInstructionForPylintCode:
    """Test cases for get_direct_instruction_for_pylint_code function."""

    def test_known_codes(self) -> None:
        """Test instructions for known pylint codes."""
        # Test a few known codes
        instruction_r0902 = get_direct_instruction_for_pylint_code("R0902")
        assert (
            instruction_r0902 is not None and "Refactor the class" in instruction_r0902
        )

        instruction_c0411 = get_direct_instruction_for_pylint_code("C0411")
        assert (
            instruction_c0411 is not None
            and "Organize your imports" in instruction_c0411
        )

        instruction_w0612 = get_direct_instruction_for_pylint_code("W0612")
        assert (
            instruction_w0612 is not None
            and "use the variable or remove" in instruction_w0612
        )

        instruction_w0621 = get_direct_instruction_for_pylint_code("W0621")
        assert (
            instruction_w0621 is not None
            and "Avoid shadowing variables" in instruction_w0621
        )

        instruction_w0311 = get_direct_instruction_for_pylint_code("W0311")
        assert instruction_w0311 is not None and "4 spaces" in instruction_w0311

    def test_unknown_code(self) -> None:
        """Test that unknown codes return None."""
        assert get_direct_instruction_for_pylint_code("X9999") is None
        assert get_direct_instruction_for_pylint_code("") is None
        assert get_direct_instruction_for_pylint_code("INVALID") is None


class TestGetPromptForKnownPylintCode:
    """Test cases for get_prompt_for_known_pylint_code function."""

    def test_known_code_with_messages(self) -> None:
        """Test generating prompt for a known code with messages."""
        messages = [
            PylintMessage(
                type="warning",
                module="test_module",
                obj="test_function",
                line=10,
                column=5,
                path="/home/user/project/src/test.py",
                symbol="unused-variable",
                message="Unused variable 'x'",
                message_id="W0612",
            ),
            PylintMessage(
                type="warning",
                module="test_module",
                obj="another_function",
                line=20,
                column=10,
                path="/home/user/project/src/test.py",
                symbol="unused-variable",
                message="Unused variable 'y'",
                message_id="W0612",
            ),
        ]

        result = PylintResult(return_code=0, messages=messages)
        prompt = get_prompt_for_known_pylint_code("W0612", "/home/user/project", result)

        assert prompt is not None
        assert "W0612" in prompt
        assert "use the variable or remove" in prompt
        # Check that the normalized path appears in the prompt
        # The path could be represented as src/test.py or src\\\\test.py in JSON
        assert any(
            path in prompt for path in ["src/test.py", "src\\\\test.py", "src\\test.py"]
        )
        assert "test_function" in prompt
        assert "another_function" in prompt
        assert "line" in prompt
        assert "10" in prompt
        assert "20" in prompt

    def test_unknown_code_returns_none(self) -> None:
        """Test that unknown codes return None."""
        messages = [
            PylintMessage(
                type="error",
                module="test",
                obj="",
                line=1,
                column=1,
                path="test.py",
                symbol="unknown",
                message="Test",
                message_id="X9999",
            ),
        ]

        result = PylintResult(return_code=0, messages=messages)
        prompt = get_prompt_for_known_pylint_code("X9999", "/project", result)

        assert prompt is None


class TestGetPromptForUnknownPylintCode:
    """Test cases for get_prompt_for_unknown_pylint_code function."""

    def test_unknown_code_prompt(self) -> None:
        """Test generating prompt for an unknown code."""
        messages = [
            PylintMessage(
                type="error",
                module="test_module",
                obj="test_function",
                line=10,
                column=5,
                path="/home/user/project/src/test.py",
                symbol="some-unknown-check",
                message="Some unknown issue",
                message_id="X9999",
            ),
        ]

        result = PylintResult(return_code=0, messages=messages)
        prompt = get_prompt_for_unknown_pylint_code(
            "X9999", "/home/user/project", result
        )

        assert prompt is not None
        assert "X9999" in prompt
        assert "some-unknown-check" in prompt
        assert "Please do two things:" in prompt
        assert "provide 1 direct instruction" in prompt
        assert "apply that instruction" in prompt
        # Check that the normalized path appears in the prompt
        # The path could be represented as src/test.py or src\\\\test.py in JSON
        assert any(
            path in prompt for path in ["src/test.py", "src\\\\test.py", "src\\test.py"]
        )
        assert "test_function" in prompt
        assert "Some unknown issue" in prompt

    def test_multiple_messages_same_code(self) -> None:
        """Test generating prompt for multiple messages with the same unknown code."""
        messages = [
            PylintMessage(
                type="error",
                module="module1",
                obj="func1",
                line=10,
                column=5,
                path="/project/src/file1.py",
                symbol="custom-check",
                message="Issue 1",
                message_id="Z0001",
            ),
            PylintMessage(
                type="error",
                module="module2",
                obj="func2",
                line=20,
                column=10,
                path="/project/src/file2.py",
                symbol="custom-check",
                message="Issue 2",
                message_id="Z0001",
            ),
        ]

        result = PylintResult(return_code=0, messages=messages)
        prompt = get_prompt_for_unknown_pylint_code("Z0001", "/project", result)

        assert prompt is not None
        assert "Z0001" in prompt
        assert "custom-check" in prompt
        assert "module1" in prompt
        assert "module2" in prompt
        assert "func1" in prompt
        assert "func2" in prompt
        # Check that normalized paths appear in the prompt
        # The paths could be represented as src/file.py or src\\\\file.py in JSON
        assert any(
            path in prompt
            for path in ["src/file1.py", "src\\\\file1.py", "src\\file1.py"]
        )
        assert any(
            path in prompt
            for path in ["src/file2.py", "src\\\\file2.py", "src\\file2.py"]
        )


class TestGetPylintPrompt:
    """Test cases for get_pylint_prompt function."""

    def test_get_pylint_prompt_includes_warning_codes(self) -> None:
        """Warning-level codes are included in output (no category filtering)."""
        messages = [
            PylintMessage(
                type="warning",
                module="test_module",
                obj="my_function",
                line=5,
                column=0,
                path="/project/src/test.py",
                symbol="unused-argument",
                message="Unused argument 'arg'",
                message_id="W0613",
            ),
        ]
        mock_result = PylintResult(return_code=4, messages=messages)

        with patch(
            "mcp_tools_py.code_checker_pylint.reporting.get_pylint_results",
            return_value=mock_result,
        ):
            prompt = get_pylint_prompt("/project", python_executable=sys.executable)

        assert prompt is not None
        assert "W0613" in prompt


class TestGetPylintPromptMaxIssues:
    """Test cases for get_pylint_prompt with max_issues parameter."""

    def _make_messages(
        self,
        specs: list[tuple[str, str, str, int]],
    ) -> list[PylintMessage]:
        """Create messages from specs: [(message_id, symbol, type, count), ...]."""
        messages: list[PylintMessage] = []
        for message_id, symbol, msg_type, count in specs:
            for i in range(count):
                messages.append(
                    PylintMessage(
                        type=msg_type,
                        module="test_module",
                        obj=f"func_{i}",
                        line=10 + i,
                        column=0,
                        path=f"/project/src/file_{i}.py",
                        symbol=symbol,
                        message=f"Issue {message_id} occurrence {i}",
                        message_id=message_id,
                    )
                )
        return messages

    def test_zero_issues_returns_none(self) -> None:
        """No messages returns None (unchanged behavior)."""
        mock_result = PylintResult(return_code=0, messages=[])
        with patch(
            "mcp_tools_py.code_checker_pylint.reporting.get_pylint_results",
            return_value=mock_result,
        ):
            result = get_pylint_prompt("/project", python_executable=sys.executable)
        assert result is None

    def test_max_issues_default_one_detail_plus_summary(self) -> None:
        """Default max_issues=1: first type detailed, rest in summary."""
        messages = self._make_messages(
            [
                ("E0602", "undefined-variable", "error", 3),
                ("W0613", "unused-argument", "warning", 4),
                ("C0411", "wrong-import-order", "convention", 2),
            ]
        )
        mock_result = PylintResult(return_code=4, messages=messages)

        with patch(
            "mcp_tools_py.code_checker_pylint.reporting.get_pylint_results",
            return_value=mock_result,
        ):
            prompt = get_pylint_prompt("/project", python_executable=sys.executable)

        assert prompt is not None
        # First type (error, highest severity) should be detailed
        assert "E0602" in prompt
        # Summary section for remaining types
        assert "W0613 unused-argument: 4 occurrences" in prompt
        assert "C0411 wrong-import-order: 2 occurrences" in prompt
        # Hint to see more
        assert "max_issues=" in prompt

    def test_max_issues_zero_stats_only(self) -> None:
        """max_issues=0: only stats, no detailed output."""
        messages = self._make_messages(
            [
                ("E0602", "undefined-variable", "error", 3),
                ("W0613", "unused-argument", "warning", 4),
            ]
        )
        mock_result = PylintResult(return_code=4, messages=messages)

        with patch(
            "mcp_tools_py.code_checker_pylint.reporting.get_pylint_results",
            return_value=mock_result,
        ):
            prompt = get_pylint_prompt(
                "/project", python_executable=sys.executable, max_issues=0
            )

        assert prompt is not None
        # Stats header
        assert "2 issue types" in prompt
        assert "7 total occurrences" in prompt
        # Per-type counts
        assert "E0602 undefined-variable: 3 occurrences" in prompt
        assert "W0613 unused-argument: 4 occurrences" in prompt
        # Hint
        assert "max_issues>=1 to see details" in prompt
        # No detailed location data (no JSON blocks)
        assert "locations in the source code" not in prompt

    def test_max_issues_greater_than_types(self) -> None:
        """max_issues exceeds type count: all detailed, no summary, no hint."""
        messages = self._make_messages(
            [
                ("E0602", "undefined-variable", "error", 2),
                ("W0613", "unused-argument", "warning", 1),
            ]
        )
        mock_result = PylintResult(return_code=4, messages=messages)

        with patch(
            "mcp_tools_py.code_checker_pylint.reporting.get_pylint_results",
            return_value=mock_result,
        ):
            prompt = get_pylint_prompt(
                "/project", python_executable=sys.executable, max_issues=5
            )

        assert prompt is not None
        # Both types should have detailed output
        assert "E0602" in prompt
        assert "W0613" in prompt
        # No summary section
        assert "additional issue type" not in prompt
        # No hint
        assert "Use max_issues=" not in prompt

    def test_location_cap_at_50(self) -> None:
        """Issue type with 60 occurrences: only 50 shown, overflow note appended."""
        messages = self._make_messages(
            [
                ("W0613", "unused-argument", "warning", 60),
            ]
        )
        mock_result = PylintResult(return_code=4, messages=messages)

        with patch(
            "mcp_tools_py.code_checker_pylint.reporting.get_pylint_results",
            return_value=mock_result,
        ):
            prompt = get_pylint_prompt(
                "/project", python_executable=sys.executable, max_issues=1
            )

        assert prompt is not None
        assert "W0613" in prompt
        # Overflow note
        assert "10 more occurrences" in prompt
        # Verify the cap constant is 50
        assert MAX_LOCATIONS_PER_ISSUE == 50

    def test_error_passthrough_unchanged(self) -> None:
        """Pylint error returns error string (unchanged behavior)."""
        mock_result = PylintResult(return_code=1, messages=[], error="Pylint timed out")
        with patch(
            "mcp_tools_py.code_checker_pylint.reporting.get_pylint_results",
            return_value=mock_result,
        ):
            result = get_pylint_prompt("/project", python_executable=sys.executable)

        assert result is not None
        assert "Pylint timed out" in result
