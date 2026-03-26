"""Tests for UtilityTools class with sleep tool."""

from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.utility_tools import UtilityTools


def test_utility_tools_registers_sleep_tool() -> None:
    """Test that UtilityTools.register() registers the sleep tool on an MCP server."""
    mock_mcp = MagicMock()
    mock_decorator = MagicMock(side_effect=lambda fn: fn)
    mock_mcp.tool.return_value = mock_decorator

    tools = UtilityTools()
    tools.register(mock_mcp)

    assert mock_mcp.tool.call_count == 1


@pytest.mark.parametrize(
    "sleep_seconds, expected_message",
    [
        (5.0, "Slept for 5.0 seconds."),
        (10.0, "Slept for 10.0 seconds."),
        (0, "Slept for 0 seconds."),
        (300, "Slept for 300 seconds."),
    ],
)
def test_sleep_valid_values(sleep_seconds: float, expected_message: str) -> None:
    """Test sleep tool with valid values calls time.sleep and returns confirmation."""
    mock_mcp = MagicMock()
    mock_decorator = MagicMock(side_effect=lambda fn: fn)
    mock_mcp.tool.return_value = mock_decorator

    tools = UtilityTools()
    tools.register(mock_mcp)

    # Get the registered sleep function
    sleep_fn = mock_decorator.call_args_list[0][0][0]

    with patch("mcp_tools_py.utility_tools.time.sleep") as mock_sleep:
        result = sleep_fn(sleep_seconds=sleep_seconds)

    mock_sleep.assert_called_once_with(sleep_seconds)
    assert result == expected_message


@pytest.mark.parametrize(
    "sleep_seconds, expected_error",
    [
        (-1, "Error: sleep_seconds must be >= 0."),
        (301, "Error: sleep_seconds must be <= 300."),
    ],
)
def test_sleep_invalid_values(sleep_seconds: float, expected_error: str) -> None:
    """Test sleep tool with invalid values returns error and does not call time.sleep."""
    mock_mcp = MagicMock()
    mock_decorator = MagicMock(side_effect=lambda fn: fn)
    mock_mcp.tool.return_value = mock_decorator

    tools = UtilityTools()
    tools.register(mock_mcp)

    # Get the registered sleep function
    sleep_fn = mock_decorator.call_args_list[0][0][0]

    with patch("mcp_tools_py.utility_tools.time.sleep") as mock_sleep:
        result = sleep_fn(sleep_seconds=sleep_seconds)

    mock_sleep.assert_not_called()
    assert result == expected_error
