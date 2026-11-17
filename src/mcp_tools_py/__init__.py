"""MCP Tools Py - An MCP server for running Python code checks."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("mcp-tools-py")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"

__all__ = ["__version__"]
