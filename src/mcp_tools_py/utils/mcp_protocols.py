"""Structural types for the subset of FastMCP this server uses."""

import functools
from typing import Any, Callable, Protocol, TypeVar

from mcp_tools_py.utils.report_budget import guard_output

# Type definitions for FastMCP
T = TypeVar("T")


class ToolDecorator(Protocol):
    """Protocol for an MCP tool-registration decorator."""

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Register `func` as an MCP tool and return it."""
        ...


class FastMCPProtocol(Protocol):
    """Subset of FastMCP's surface used by ToolServer."""

    def tool(self) -> ToolDecorator:
        """Return a decorator that registers a tool."""
        ...

    def run(self) -> None:
        """Run the MCP server event loop."""
        ...


GUARD_ATTR = "__output_guarded__"


class GuardedMCP:
    """FastMCPProtocol wrapper whose tool() bounds every string a tool returns."""

    def __init__(self, mcp: FastMCPProtocol) -> None:
        """Wrap `mcp`; registrations go through the global output guard."""
        self._mcp = mcp

    def tool(self) -> ToolDecorator:
        """Return a decorator that guards `func`'s output and registers it."""
        register = self._mcp.tool()

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            @functools.wraps(func)
            def guarded(*args: Any, **kwargs: Any) -> Any:
                result = func(*args, **kwargs)
                if isinstance(result, str):
                    return guard_output(result)
                return result

            setattr(guarded, GUARD_ATTR, True)
            return register(guarded)

        return decorator

    def run(self) -> None:
        """Run the wrapped MCP server."""
        self._mcp.run()
