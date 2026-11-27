"""Each call site passes its own tool to resolve_target_directories.

The resolver decides per tool which folders to cover, so a call site that
passes the wrong tool would check the wrong folders.  Each test patches the
resolver to return an error string, so no checker actually runs, and asserts
the call site both passed the right tool and returned the resolver's error.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.formatter.formatter_tools import FormatterTools
from mcp_tools_py.toolkit import _run_format
from mcp_tools_py.toolkit_checks import _CHECK_RUNNERS
from mcp_tools_py.utils.tool_context import ToolContext

_SENTINEL = "Error resolving target directories: sentinel"
_RUFF_FORMATTER = '[tool.mcp-tools-py]\nformatter = "ruff"\n'


def _write_ruff_formatter_config(tool_context: ToolContext) -> None:
    """Declare the ruff formatter so the formatter steps resolve."""
    (tool_context.project_dir / "pyproject.toml").write_text(
        _RUFF_FORMATTER, encoding="utf-8"
    )


def _capture_tools(tool_context: ToolContext) -> dict[str, Any]:
    """Register formatter and checker tools and capture them by name."""
    captured_fns: dict[str, Any] = {}

    def capture(fn: Any) -> Any:
        captured_fns[fn.__name__] = fn
        return fn

    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = capture
    FormatterTools(tool_context).register(mock_mcp)
    CheckerTools(tool_context).register(mock_mcp)
    return captured_fns


@pytest.mark.parametrize(
    ("function_name", "module", "expected_tool"),
    [
        ("run_format_code", "mcp_tools_py.formatter.formatter_tools", "formatter"),
        ("run_ruff_check", "mcp_tools_py.checker_tools.ruff_check_tool", "ruff"),
        ("run_ruff_fix", "mcp_tools_py.checker_tools.ruff_fix_tool", "ruff"),
        ("run_pylint_check", "mcp_tools_py.checker_tools.pylint_tool", "pylint"),
        ("run_mypy_check", "mcp_tools_py.checker_tools.mypy_tool", "mypy"),
        ("run_vulture_check", "mcp_tools_py.checker_tools.vulture_tool", "vulture"),
        ("run_bandit_check", "mcp_tools_py.checker_tools.bandit_tool", "bandit"),
    ],
)
def test_mcp_tool_passes_its_tool(
    tool_context: ToolContext, function_name: str, module: str, expected_tool: str
) -> None:
    """Each MCP tool passes its tool and returns the resolver's error."""
    _write_ruff_formatter_config(tool_context)
    function = _capture_tools(tool_context)[function_name]

    with patch(
        f"{module}.resolve_target_directories", return_value=_SENTINEL
    ) as mock_resolve:
        result = function()

    assert _SENTINEL in result
    assert mock_resolve.call_args.args == (
        str(tool_context.project_dir),
        None,
        expected_tool,
    )


@pytest.mark.parametrize("name", ["mypy", "pylint", "vulture", "ruff", "bandit"])
def test_check_runner_passes_its_tool(tool_context: ToolContext, name: str) -> None:
    """Each toolkit check runner passes its tool and reports the resolver's error."""
    with patch(
        "mcp_tools_py.toolkit_checks.resolve_target_directories",
        return_value=_SENTINEL,
    ) as mock_resolve:
        result = _CHECK_RUNNERS[name](tool_context, "full")

    assert result.status == "error"
    assert result.summary == _SENTINEL
    assert mock_resolve.call_args.args == (str(tool_context.project_dir), None, name)


def test_toolkit_format_passes_formatter(tool_context: ToolContext) -> None:
    """The toolkit format action passes "formatter" and reports the error."""
    _write_ruff_formatter_config(tool_context)

    with patch(
        "mcp_tools_py.toolkit.resolve_target_directories", return_value=_SENTINEL
    ) as mock_resolve:
        result = _run_format(tool_context, "check")

    assert result.status == "error"
    assert result.summary == _SENTINEL
    assert mock_resolve.call_args.args[2] == "formatter"
