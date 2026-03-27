# Issue #124: feat(checker_tools): add vulture dead-code check MCP tool

## Summary

Add a `run_vulture_check` MCP tool for dead-code detection. The tool follows the existing `lint-imports` pattern: binary lookup in venv, `execute_command()` for execution, raw output returned to the caller. Implementation is inline in `checker_tools.py` (no separate module).

## Architectural / Design Changes

### Server Layer (`server.py`)
- **New init param**: `vulture_whitelist: str` — server-level config for the whitelist file path, defaulting to `"vulture_whitelist.py"`. Resolved relative to `project_dir`.
- **New binary attribute**: `self._vulture_binary` — resolved path to the vulture binary in the venv, following the exact pattern of `self._lint_imports_binary`.
- **Extended availability check**: `_check_tool_availability()` gains a `"vulture"` entry using binary file-existence check (same as lint-imports).

### Tool Layer (`checker_tools.py`)
- **New registration method**: `_register_vulture(mcp)` — registers `run_vulture_check` as an MCP tool. Follows the lint-imports pattern: build command list, call `execute_command()`, return combined stdout+stderr.
- **No formatter method** — raw output like lint-imports, no parsing needed.
- **Tool count**: 4 → 5 registered tools.

### CLI Layer (`main.py`)
- **New CLI arg**: `--vulture-whitelist` passed through `create_server()` to `CodeCheckerServer.__init__()`.

### Dependencies (`pyproject.toml`)
- ✅ **Already applied**: `vulture>=2.13` and `import-linter>=2.0` moved from `[dev]` extras to core `dependencies`.

### No New Modules Created
The issue explicitly requires inline implementation. No `code_checker_vulture/` package.

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | ✅ Done — moved `vulture` and `import-linter` to core dependencies |
| `src/mcp_tools_py/server.py` | Add `vulture_whitelist` param, `_vulture_binary` resolution, availability check |
| `src/mcp_tools_py/checker_tools.py` | Add `_register_vulture()` method, call from `register()` |
| `src/mcp_tools_py/main.py` | Add `--vulture-whitelist` CLI arg, wire to `create_server()` |
| `vulture_whitelist.py` | Add `_.run_vulture_check` entry |
| `tests/test_checker_tools.py` | Update fixture, registration count 4→5, add vulture tests |
| `tests/test_tool_availability.py` | Update expected availability dicts to include `"vulture"` |

## Implementation Steps

- **Step 1**: `server.py` + `tests/test_tool_availability.py` — vulture binary resolution, availability check, whitelist param
- **Step 2**: `checker_tools.py` + `tests/test_checker_tools.py` — register vulture tool, test execution paths
- **Step 3**: `main.py` + `vulture_whitelist.py` — CLI wiring and whitelist entry
