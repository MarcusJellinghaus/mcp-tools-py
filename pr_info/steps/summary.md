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

Three targeted fixes, each addressing one root cause:

| Fix | What | How |
|-----|------|-----|
| Disable rope cache | Set `ropefolder=None` in `Project()` constructor | One-line change in `_with_rope_project()` |
| Gitignore-aware filtering | Parse `.gitignore` via `pathspec` (already a dependency) and pass patterns to rope's `ignored_resources` | ~15 lines in `rope_tools.py` |
| Timeout via multiprocessing | Wrap each rope operation in `multiprocessing.Process` with configurable timeout (default: 120s) | New `_run_with_timeout()` wrapper function |

## Architectural / Design Changes

### New data flow: timeout parameter

```
CLI (--refactoring-timeout)
  → main.py (parse_args)
    → server.py (CodeCheckerServer.__init__)
      → refactoring/__init__.py (RefactoringTools.__init__)
        → rope_tools.py (each public function receives `timeout` param)
          → _run_with_timeout() (multiprocessing.Process wrapper)
```

### Modified component: `_with_rope_project()` context manager

Currently creates a bare `Project(str(project_dir))`. After changes:
- Sets `ropefolder=None` (disables persistent cache)
- Accepts `ignored_resources` patterns derived from `.gitignore`

### New internal function: `_run_with_timeout()`

A minimal `multiprocessing.Process` + `Queue` wrapper that:
1. Spawns a child process running the rope operation
2. Joins with timeout
3. Returns result string on success, or kills process and returns error on timeout

This is **not** a generic framework — it's a single focused function used only by
the three rope entry points.

### No new dependencies

`pathspec>=0.12.1` is already in `pyproject.toml`. No new packages needed.

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/main.py` | Add `--refactoring-timeout` CLI argument |
| `src/mcp_tools_py/server.py` | Add `refactoring_timeout` parameter to `CodeCheckerServer` and `create_server` |
| `src/mcp_tools_py/refactoring/__init__.py` | Accept `timeout` in `RefactoringTools.__init__`, pass to rope functions |
| `src/mcp_tools_py/refactoring/rope_tools.py` | `ropefolder=None`, gitignore filtering, `_run_with_timeout()` wrapper, `timeout` param on public functions |
| `tests/test_refactoring/test_rope_tools.py` | Add tests for timeout, ropefolder, gitignore filtering |

## Files NOT Modified

| File | Reason |
|------|--------|
| `pyproject.toml` | `pathspec` already a dependency |
| `src/mcp_tools_py/refactoring/jedi_tools.py` | Jedi tools work fine, no changes needed |
| `src/mcp_tools_py/checker_tools.py` | Checker tools unrelated |

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | CLI arg + server/refactoring plumbing for `refactoring_timeout` | `step_1.md` |
| 2 | Disable `.ropeproject/` cache (`ropefolder=None`) | `step_2.md` |
| 3 | Gitignore-aware file filtering for rope via `pathspec` | `step_3.md` |
| 4 | Multiprocessing timeout wrapper (`_run_with_timeout`) | `step_4.md` |
