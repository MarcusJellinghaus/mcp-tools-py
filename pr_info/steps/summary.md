# Issue #112: Fix rope-based mutation tools hanging indefinitely

## Problem

All three rope-based mutation tools (`rename_symbol`, `move_symbol`, `move_module`) hang
indefinitely. Read-only jedi-based tools work fine on the same symbols.

## Root Causes

1. **No timeout** — Rope's `get_changes()` performs a full project scan with zero timeout
   protection, blocking the MCP server event loop indefinitely.
2. **Stale `.ropeproject/` cache** — Rope creates a persistent `.ropeproject/` folder. Stale
   cache can cause hangs when rope tries to reconcile state.
3. **Rope scans all files** — Unlike jedi's read-only operations, rope must parse every Python
   file. The default ignored patterns miss `__pycache__/`, `node_modules/`, `.venv/`, etc.

## Solution Overview

| Fix | What | How |
|-----|------|-----|
| Disable rope cache | Set `ropefolder=None` in `Project()` constructor | One-line change in `_with_rope_project()` |
| Gitignore-aware filtering | Copy `read_gitignore_rules()` and `apply_gitignore_filter()` from `p_workspace` using `igittigitt` library, convert to rope's `ignored_resources` | ~40 lines in `rope_tools.py` |
| ~~Timeout via multiprocessing~~ | ~~Wrap each rope operation in `multiprocessing.Process`~~ | Replaced by Step 3 |
| **Subprocess isolation** | Run rope in isolated subprocess via `rope_cli.py` | Same pattern as pytest/pylint/mypy runners |

## Architectural / Design Changes

### Data flow: subprocess isolation

```
MCP tool call (sync function in __init__.py)
  → rope_tools.py::rename_symbol()       # public API, validates inputs
    → _run_rope_subprocess()              # builds command, calls execute_command
      → subprocess_runner.py              # stdin=DEVNULL, file-based stdout
        → rope_cli.py::main()             # isolated process, parses JSON args
          → _rename_symbol_impl()         # actual rope work
            → JSON result on stdout
```

The subprocess approach was chosen because the MCP server uses stdin/stdout for
JSON-RPC transport. Windows `spawn` causes child processes to inherit these
pipes, breaking the transport. The `execute_command` pattern (used by
pytest/pylint/mypy runners) provides complete process isolation with
`stdin=DEVNULL` and file-based stdout capture.

### Modified component: `_with_rope_project()` context manager

- Sets `ropefolder=None` (disables persistent cache)
- Accepts `ignored_resources` patterns derived from `.gitignore` via `igittigitt`

### Gitignore utilities (copied from p_workspace)

`read_gitignore_rules()` and `apply_gitignore_filter()` are copied one-to-one from
`p_workspace/src/mcp_workspace/file_tools/directory_utils.py`. They use `igittigitt`
(NOT `pathspec`). A TODO comment marks them for future extraction into shared `mcp_utils`.

### `rope_cli.py` — CLI entry point

Accepts `<operation> <json_args>`, dispatches to the appropriate `_*_impl`
function, and outputs the result as `{"result": "..."}` JSON on stdout.

### `_run_rope_subprocess()` — subprocess dispatcher

Builds a command `[python, -m, mcp_tools_py.refactoring.rope_cli, op, json]`
and calls `execute_command()` from `subprocess_runner.py`. Handles timeout,
execution errors, and non-zero exit codes. Parses JSON output.

## New dependency

`igittigitt` added to `pyproject.toml`. Replaces the original plan to use `pathspec`.

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Add `igittigitt` dependency |
| `src/mcp_tools_py/main.py` | Add `--refactoring-timeout` CLI argument |
| `src/mcp_tools_py/server.py` | Add `refactoring_timeout` parameter to `CodeCheckerServer` and `create_server` |
| `src/mcp_tools_py/refactoring/__init__.py` | Sync tools with `@log_function_call`, pass `timeout` to rope functions |
| `src/mcp_tools_py/refactoring/rope_tools.py` | `ropefolder=None`, gitignore filtering, `_run_rope_subprocess()`, `rope_cli.py` dispatch |
| `src/mcp_tools_py/refactoring/rope_cli.py` | NEW — CLI entry point for isolated subprocess execution |
| `tests/test_refactoring/test_rope_tools.py` | Tests for ropefolder, gitignore filtering |
| `tests/test_refactoring/test_integration.py` | Hang-regression tests, end-to-end workflow tests |

## Files NOT Modified

| File | Reason |
|------|--------|
| `src/mcp_tools_py/refactoring/jedi_tools.py` | Jedi tools work fine, no changes needed |
| `src/mcp_tools_py/checker_tools.py` | Checker tools unrelated |

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Disable `.ropeproject/` cache + gitignore-aware filtering via `igittigitt` | `step_1.md` |
| 2 | ~~Multiprocessing timeout wrapper~~ (replaced by Step 3) | `step_2.md` |
| 3 | Replace multiprocessing with subprocess isolation via `rope_cli.py` | `step_3.md` |
| 4 | Cleanup: remove dead code and fragile real-project-dir tests | `step_4.md` |
| 5 | Robustness: structured error handling in `rope_cli.py` | `step_5.md` |
