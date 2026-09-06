"""All five tool registrars take the same argument: a ToolContext."""

from unittest.mock import MagicMock

from mcp_tools_py.checker_tools import CheckerTools
from mcp_tools_py.formatter import FormatterTools
from mcp_tools_py.inspect_library import InspectTools
from mcp_tools_py.refactoring import RefactoringTools
from mcp_tools_py.utility_tools import UtilityTools
from mcp_tools_py.utils.tool_context import ToolContext

# 9 checkers + 1 formatter + 5 refactoring + 1 utility + 1 inspection.
EXPECTED_TOOL_COUNT = 17


def test_every_registrar_takes_a_tool_context(tool_context: ToolContext) -> None:
    """One context constructs all five registrars, and they register 17 tools."""
    mcp = MagicMock()
    mcp.tool.return_value = lambda fn: fn

    CheckerTools(tool_context).register(mcp)
    FormatterTools(tool_context).register(mcp)
    RefactoringTools(tool_context).register(mcp)
    UtilityTools(tool_context).register(mcp)
    InspectTools(tool_context).register(mcp)

    assert mcp.tool.call_count == EXPECTED_TOOL_COUNT
