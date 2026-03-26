# Issue #116: Add simple sleep MCP tool

## Summary

Add a `sleep` MCP tool via a new `UtilityTools` class. This is a minimal tool that calls `time.sleep()` — no subprocess, no external scripts. It follows the existing tool registration pattern (`CheckerTools`, `RefactoringTools`).

## Architecture / Design Changes

### New module: `mcp_tools_py.utility_tools`

- **Layer**: `tool_implementation` (same as `checker_tools`, `refactoring`)
- **Dependencies**: Only `mcp_tools_py.log_utils` (for `@log_function_call` decorator)
- **Pattern**: Follows the same `register(mcp)` pattern as existing tool classes
- **Registration**: `UtilityTools().register(self.mcp)` in `server.py`

### Architecture config updates

- `tach.toml`: New `[[modules]]` entry at `tool_implementation` layer
- `.importlinter`: Add `mcp_tools_py.utility_tools` alongside `checker_tools | refactoring` in the layered contract; add to forbidden imports source for `utils`
- `server.py`: Import + register the new tool group

### No changes to

- `main.py`, `pyproject.toml`, CLI arguments, dependencies — nothing new is needed

## Files to Create

| File | Purpose |
|------|---------|
| `src/mcp_tools_py/utility_tools.py` | `UtilityTools` class with `sleep` tool |
| `tests/test_utility_tools.py` | Unit tests |

## Files to Modify

| File | Change |
|------|--------|
| `src/mcp_tools_py/server.py` | Import and register `UtilityTools` |
| `tach.toml` | Add `mcp_tools_py.utility_tools` module |
| `.importlinter` | Add to layered contract + forbidden imports |

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Create `utility_tools.py` + `test_utility_tools.py` (TDD) | `feat: add sleep MCP tool via UtilityTools class` |
| 2 | Register in `server.py` + update `tach.toml` and `.importlinter` | `feat: register UtilityTools and update architecture configs` |
