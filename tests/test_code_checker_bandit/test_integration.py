"""Integration tests for bandit checker tool registration and execution."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.code_checker_bandit.models import BanditMessage, BanditResult


def _make_mock_server(bandit_available: bool = True) -> MagicMock:
    """Create a mock ToolServer with bandit configuration."""
    server = MagicMock()
    server.project_dir = Path("/fake/project")
    server._resolved_python = "/usr/bin/python3"
    server._bandit_binary = "/mock/venv/bin/bandit" if bandit_available else None
    server._tool_availability = {"bandit": bandit_available}
    return server


def _register_and_capture(server: MagicMock) -> dict[str, object]:
    """Register checker tools and capture the registered functions."""
    registered: dict[str, object] = {}

    def capture(func: Callable[..., object]) -> Callable[..., object]:
        registered[func.__name__] = func
        return func

    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = capture

    checker = CheckerTools(server)
    checker._register_bandit(mock_mcp)
    return registered


def test_bandit_not_available_message() -> None:
    """When bandit is unavailable, the tool returns a not-available message."""
    server = _make_mock_server(bandit_available=False)
    tools = _register_and_capture(server)

    result = tools["run_bandit_check"]()  # type: ignore[operator]

    assert "bandit is not available" in result
    assert "Restart the server" in result


def test_bandit_happy_path() -> None:
    """When bandit finds issues, the formatted report is returned."""
    server = _make_mock_server(bandit_available=True)
    tools = _register_and_capture(server)

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
            "mcp_tools_py.checker_tools.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.run_bandit_check_impl",
            return_value=mock_result,
        ),
    ):
        result = tools["run_bandit_check"]()  # type: ignore[operator]

    assert "B101" in result
    assert "assert_used" in result
    assert "src/app.py" in result


def test_bandit_error_handling() -> None:
    """When bandit returns an error, the error string is returned."""
    server = _make_mock_server(bandit_available=True)
    tools = _register_and_capture(server)

    mock_result = BanditResult(
        return_code=-1,
        messages=[],
        errors=[],
        error="bandit crashed unexpectedly",
    )

    with (
        patch(
            "mcp_tools_py.checker_tools.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.run_bandit_check_impl",
            return_value=mock_result,
        ),
    ):
        result = tools["run_bandit_check"]()  # type: ignore[operator]

    assert "bandit error" in result
    assert "bandit crashed unexpectedly" in result


def test_bandit_no_issues_found() -> None:
    """When bandit finds no issues, a clean message is returned."""
    server = _make_mock_server(bandit_available=True)
    tools = _register_and_capture(server)

    mock_result = BanditResult(return_code=0, messages=[], errors=[])

    with (
        patch(
            "mcp_tools_py.checker_tools.resolve_target_directories",
            return_value=["src"],
        ),
        patch(
            "mcp_tools_py.checker_tools.run_bandit_check_impl",
            return_value=mock_result,
        ),
    ):
        result = tools["run_bandit_check"]()  # type: ignore[operator]

    assert result == "No bandit security issues found."
