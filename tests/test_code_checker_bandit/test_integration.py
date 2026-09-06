"""Integration tests for bandit checker tool registration and execution."""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

from mcp_tools_py.checker_tools import CheckerTools, bandit_tool
from mcp_tools_py.code_checker_bandit.models import BanditMessage, BanditResult
from mcp_tools_py.utils.tool_context import ToolContext


def _register_and_capture(context: ToolContext) -> dict[str, object]:
    """Register checker tools and capture the registered functions."""
    registered: dict[str, object] = {}

    def capture(func: Callable[..., object]) -> Callable[..., object]:
        registered[func.__name__] = func
        return func

    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = capture

    checker = CheckerTools(context)
    bandit_tool.register(mock_mcp, checker)
    return registered


def test_bandit_not_available_message(tool_context: ToolContext) -> None:
    """When bandit is unavailable, the tool returns a not-available message."""
    binary = tool_context.environment.binary("bandit")
    assert binary is not None
    binary.unlink()
    tools = _register_and_capture(tool_context)

    result = tools["run_bandit_check"]()  # type: ignore[operator]

    assert "bandit is not available" in result
    assert "Restart the server" in result


def test_bandit_happy_path(tool_context: ToolContext) -> None:
    """When bandit finds issues, the formatted report is returned."""
    tools = _register_and_capture(tool_context)

    messages = [
        BanditMessage(
            test_id="B101",
            test_name="assert_used",
            issue_severity="LOW",
            issue_confidence="HIGH",
            issue_text="Use of assert detected.",
            filename="src/app.py",
            line_number=10,
            more_info="https://bandit.readthedocs.io/en/latest/plugins/b101_assert_used.html",
            cwe_id=703,
            cwe_link="https://cwe.mitre.org/data/definitions/703.html",
        ),
    ]
    mock_result = BanditResult(
        return_code=1, messages=messages, errors=[], raw_output="{}"
    )

    with (
        patch(
            "mcp_tools_py.checker_tools.bandit_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.bandit_tool.run_bandit_check_impl",
            return_value=mock_result,
        ),
    ):
        result = tools["run_bandit_check"]()  # type: ignore[operator]

    assert "B101" in result
    assert "assert_used" in result
    assert "src/app.py" in result


def test_bandit_error_handling(tool_context: ToolContext) -> None:
    """When bandit returns an error, the error string is returned."""
    tools = _register_and_capture(tool_context)

    mock_result = BanditResult(
        return_code=-1,
        messages=[],
        errors=[],
        error="bandit crashed unexpectedly",
    )

    with (
        patch(
            "mcp_tools_py.checker_tools.bandit_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.bandit_tool.run_bandit_check_impl",
            return_value=mock_result,
        ),
    ):
        result = tools["run_bandit_check"]()  # type: ignore[operator]

    assert "bandit error" in result
    assert "bandit crashed unexpectedly" in result


def test_bandit_no_issues_found(tool_context: ToolContext) -> None:
    """When bandit finds no issues, a clean message is returned."""
    tools = _register_and_capture(tool_context)

    mock_result = BanditResult(return_code=0, messages=[], errors=[])

    with (
        patch(
            "mcp_tools_py.checker_tools.bandit_tool.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.bandit_tool.run_bandit_check_impl",
            return_value=mock_result,
        ),
    ):
        result = tools["run_bandit_check"]()  # type: ignore[operator]

    assert result == "No bandit security issues found."
