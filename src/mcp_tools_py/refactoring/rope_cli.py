"""CLI entry point for rope refactoring operations.

Runs rope operations in an isolated subprocess to avoid blocking
the MCP server's event loop and stdio pipes.

Usage:
    python -m mcp_tools_py.refactoring.rope_cli <operation> <json_args>

Operations: rename_symbol, move_symbol, move_module
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    """Parse CLI args and dispatch to the appropriate rope operation."""
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <operation> <json_args>", file=sys.stderr)
        sys.exit(1)

    operation = sys.argv[1]
    args = json.loads(sys.argv[2])

    # Import here to keep startup fast and isolated
    from mcp_tools_py.refactoring.rope_tools import (  # pylint: disable=import-outside-toplevel
        _move_module_impl,
        _move_symbol_impl,
        _rename_symbol_impl,
    )

    project_dir = Path(args["project_dir"])

    if operation == "rename_symbol":
        result = _rename_symbol_impl(
            project_dir,
            args["file_path"],
            args["symbol_name"],
            args["new_name"],
            args["dry_run"],
        )
    elif operation == "move_symbol":
        result = _move_symbol_impl(
            project_dir,
            args["source_file"],
            args["symbol_name"],
            args["dest_file"],
            args["dry_run"],
        )
    elif operation == "move_module":
        result = _move_module_impl(
            project_dir,
            args["source_module"],
            args["dest_package"],
            args["dry_run"],
        )
    else:
        print(f"Unknown operation: {operation}", file=sys.stderr)
        sys.exit(1)

    # Output result as JSON for structured parsing
    print(json.dumps({"result": result}))


if __name__ == "__main__":
    main()
