"""MCP Tools Py - An MCP server for running Python code checks."""

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:
    from importlib_metadata import PackageNotFoundError, version  # type: ignore

try:
    __version__ = version("mcp-tools-py")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"

__all__ = ["__version__"]
