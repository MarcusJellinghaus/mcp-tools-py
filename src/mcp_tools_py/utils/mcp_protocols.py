"""Structural types for the subset of FastMCP this server uses."""

from typing import Callable, Protocol, TypeVar

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
