# Issue #101: `get_library_source` MCP Tool — Implementation Summary

## Overview

Add a single `get_library_source` MCP tool that returns source code for any importable Python symbol, replacing ad-hoc `Bash` + `python -c "import inspect; ..."` patterns.

## Architecture & Design Changes

### New Module

- **`src/mcp_tools_py/inspect_library.py`** — Single file containing:
  - `InspectTools` class with `register()` method (mirrors `RefactoringTools` pattern)
  - `_get_library_source()` helper function with the core resolution + source retrieval logic
  - No subprocess, no models/parsers/reporting — just `importlib` + `inspect` in-process

### Registration

- `server.py` imports `InspectTools` and calls `.register(self.mcp)` alongside existing tools
- `InspectTools` takes no constructor args (no project_dir needed — works with importlib only)

### Architecture Config Updates

- **`tach.toml`**: New `mcp_tools_py.inspect_library` module in `tool_implementation` layer, depends on `log_utils`; added to `server` depends_on
- **`.importlinter`**: Added to layers alongside `checker_tools | refactoring`; ignore rule for `TYPE_CHECKING` import of `FastMCPProtocol`

### New Test File

- **`tests/test_inspect_library.py`** — Unit tests (mocked) + real-import tests (stdlib + structlog, no markers needed)

## Files Created

| File | Purpose |
|------|---------|
| `src/mcp_tools_py/inspect_library.py` | `InspectTools` class + core logic |
| `tests/test_inspect_library.py` | All unit tests |

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/server.py` | Import + register `InspectTools` |
| `tach.toml` | Add `inspect_library` module boundary |
| `.importlinter` | Add `inspect_library` to layers + ignore rule |

## Tool API

```python
get_library_source(
    import_path: str,      # e.g. "rope.refactor.move.MoveModule"
    max_lines: int = 200   # truncate output; must be >= 1
) -> str
```

## Core Algorithm (pseudocode)

```
validate max_lines >= 1
walk backwards splitting import_path on "." trying importlib.import_module()
getattr chain for remaining path segments
call inspect.getsource() on resolved object
if lines > max_lines: truncate + append note
return source text
```

## Error Handling

| Scenario | Response |
|----------|----------|
| `max_lines < 1` | `"max_lines must be a positive integer (>= 1), got: {value}"` |
| Module not found | `"Module '{name}' not found"` |
| Symbol not found | Lists available symbols (sorted, capped at 50, type-annotated) |
| Built-in/C extension | `"Source not available for '{name}' (built-in/C extension)..."` |

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Core logic: `inspect_library.py` with `_get_library_source()` + unit tests (mocked) | tests + implementation |
| 2 | Real-import tests + MCP tool registration in `server.py` | tests + wiring |
| 3 | Architecture configs: `tach.toml` + `.importlinter` | config updates |
