"""Library source inspection tools for MCP server."""

import importlib
import inspect
import types
from typing import TYPE_CHECKING, Any, Callable, Union, cast

from mcp_tools_py.log_utils import log_function_call

if TYPE_CHECKING:
    from mcp_tools_py.server import FastMCPProtocol


def _get_library_source(import_path: str, max_lines: int = 200) -> str:
    """Retrieve source code for any importable Python symbol.

    Args:
        import_path: Dotted import path (e.g. "os.path.join" or "json.JSONEncoder").
        max_lines: Maximum number of source lines to return. Must be >= 1.

    Returns:
        Source code string, or an error message if resolution fails.
    """
    if max_lines < 1:
        return f"max_lines must be a positive integer (>= 1), got: {max_lines}"

    parts = import_path.split(".")

    # Walk backwards to find the longest importable module prefix
    module: types.ModuleType | None = None
    remaining: list[str] = []
    for i in range(len(parts), 0, -1):
        module_path = ".".join(parts[:i])
        try:
            module = importlib.import_module(module_path)
            remaining = parts[i:]
            break
        except (ImportError, ModuleNotFoundError):
            continue

    if module is None:
        return f"Module '{import_path}' not found"

    # Walk the remaining attribute chain
    obj: object = module
    for attr_name in remaining:
        try:
            obj = getattr(obj, attr_name)
        except AttributeError:
            module_name = module.__name__
            # List available symbols, sorted, capped at 50, type-annotated
            members = inspect.getmembers(obj)
            symbols: list[str] = []
            for name, value in sorted(members, key=lambda m: m[0]):
                if name.startswith("_"):
                    continue
                kind = type(value).__name__
                if isinstance(value, type):
                    kind = "class"
                elif callable(value):
                    kind = "function"
                elif isinstance(value, types.ModuleType):
                    kind = "module"
                symbols.append(f"  {name} ({kind})")
                if len(symbols) >= 50:
                    break
            symbol_list = "\n".join(symbols)
            return (
                f"'{attr_name}' not found in module '{module_name}'.\n\n"
                f"Available symbols:\n{symbol_list}"
            )

    # Try to get source
    try:
        # obj is resolved via importlib/getattr so it's always an inspectable symbol
        source = inspect.getsource(
            cast(Union[types.ModuleType, type, Callable[..., Any]], obj)
        )
    except (TypeError, OSError):
        name = import_path.split(".")[-1]
        return (
            f"Source not available for '{name}' (built-in/C extension). "
            "Only pure-Python symbols have inspectable source."
        )

    lines = source.splitlines()
    if len(lines) > max_lines:
        truncated = "\n".join(lines[:max_lines])
        total = len(lines)
        return (
            f"{truncated}\n"
            f"... truncated (showing {max_lines} of {total} lines). "
            "Use max_lines to see more."
        )

    return source


class InspectTools:
    """Registers library inspection tools on an MCP server."""

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all inspection tools."""
        self._register_get_library_source(mcp)

    def _register_get_library_source(self, mcp: "FastMCPProtocol") -> None:
        """Register the get_library_source tool."""

        @mcp.tool()
        @log_function_call
        def get_library_source(import_path: str, max_lines: int = 200) -> str:
            """Return the source code of any importable Python symbol.

            Resolves dotted import paths (e.g. "json.JSONEncoder",
            "os.path.join") and returns the source code. Useful for
            understanding library internals without leaving the editor.

            Args:
                import_path: Dotted Python import path to resolve.
                max_lines: Maximum source lines to return (default 200).
            """
            return _get_library_source(import_path, max_lines)
