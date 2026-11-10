"""Every registered tool's string output passes through the global guard."""

from pathlib import Path
from typing import Any, Callable

from mcp_tools_py.server import ToolServer
from mcp_tools_py.utils.mcp_protocols import GUARD_ATTR, GuardedMCP
from mcp_tools_py.utils.report_budget import GUARD_HINT, GUARD_LINES

EXPECTED_TOOL_COUNT = 19


def _tools(server: ToolServer) -> list[Any]:
    return list(server.mcp._tool_manager.list_tools())  # type: ignore[attr-defined]


def test_every_registered_tool_is_guarded(tmp_path: Path) -> None:
    """All 19 tools registered by ToolServer carry the guard marker."""
    tools = _tools(ToolServer(tmp_path))
    assert len(tools) == EXPECTED_TOOL_COUNT
    for tool in tools:
        assert getattr(tool.fn, GUARD_ATTR, False), tool.name


def test_guarded_tool_keeps_its_parameter_schema(tmp_path: Path) -> None:
    """The wrapper keeps the wrapped signature, so the schema lists parameters."""
    tools = {tool.name: tool for tool in _tools(ToolServer(tmp_path))}
    assert "max_issues" in tools["run_mypy_check"].parameters["properties"]


class _FakeMCP:
    def __init__(self) -> None:
        self.registered: list[Callable[..., Any]] = []

    def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self.registered.append(func)
            return func

        return decorator

    def run(self) -> None:
        """Do nothing."""


def test_guard_bounds_string_results_and_passes_dicts() -> None:
    """A 2000-line string is bounded with the hint; a dict is untouched."""
    fake = _FakeMCP()
    guarded = GuardedMCP(fake)

    @guarded.tool()
    def big() -> str:
        return "\n".join(f"line {i}" for i in range(2000))

    @guarded.tool()
    def data() -> dict[str, int]:
        return {"a": 1}

    result = fake.registered[0]()
    assert len(result.splitlines()) <= GUARD_LINES
    assert result.endswith(GUARD_HINT)
    assert fake.registered[1]() == {"a": 1}
    assert big.__name__ == "big"
    assert data() == {"a": 1}
