"""Shared helpers for the tool-availability tests."""

import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock


def _create_server(**kwargs: Any) -> Any:
    """Construct a real ToolServer from the given keyword arguments.

    Mocks nothing: each caller sets up whatever patches it needs around
    the call.

    Returns:
        The constructed ToolServer.
    """
    from mcp_tools_py.server import ToolServer

    return ToolServer(**kwargs)


def _dummy_python(tmp_path: Path, *scripts: str) -> str:
    """Create a script directory with a dummy interpreter and console scripts.

    Pins the directory that availability detection searches, so tests do not
    depend on what the ambient interpreter happens to have installed.

    Returns:
        Path to the dummy interpreter, for passing as `python_executable`.
    """
    script_dir = tmp_path / "scripts"
    script_dir.mkdir(exist_ok=True)
    suffix = ".exe" if os.name == "nt" else ""
    python = script_dir / f"python{suffix}"
    python.write_text("")
    for name in scripts:
        (script_dir / f"{name}{suffix}").write_text("")
    return str(python)


def _capture_tools(mock_fastmcp: MagicMock) -> dict[str, Any]:
    """Set up tool capture on a mocked FastMCP instance.

    Returns a dict that will be populated with {func_name: func} as tools
    are registered during server construction.
    """
    registered_tools: dict[str, Any] = {}

    def capture_tool(func: Any) -> Any:
        registered_tools[func.__name__] = func
        return func

    mock_fastmcp.return_value.tool.return_value = capture_tool
    return registered_tools
