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
| Timeout via multiprocessing | Wrap each rope operation in `multiprocessing.Process` with configurable timeout (default: 120s) | New `_run_with_timeout()` wrapper |

## Architectural / Design Changes

### New data flow: timeout parameter

```
CLI (--refactoring-timeout)
  → main.py (parse_args)
    → server.py (CodeCheckerServer.__init__)
      → refactoring/__init__.py (RefactoringTools.__init__)
        → rope_tools.py (each public function receives timeout param)
          → _run_with_timeout() (multiprocessing.Process wrapper)
```

### Modified component: `_with_rope_project()` context manager

Currently creates a bare `Project(str(project_dir))`. After changes:
- Sets `ropefolder=None` (disables persistent cache)
- Accepts `ignored_resources` patterns derived from `.gitignore` via `igittigitt`

### Gitignore utilities (copied from p_workspace)

`read_gitignore_rules()` and `apply_gitignore_filter()` are copied one-to-one from
`p_workspace/src/mcp_workspace/file_tools/directory_utils.py`. They use `igittigitt`
(NOT `pathspec`). A TODO comment marks them for future extraction into shared `mcp_utils`.

### New internal function: `_run_with_timeout()`

A `multiprocessing.Process` + `Queue` wrapper that:
1. Spawns a child process running the rope operation
2. Calls `queue.get(timeout=...)` before `process.join()` (avoids Windows pipe deadlock)
3. Returns result string on success, or kills process and returns error on timeout

Each `_*_impl` function creates its own rope `Project` inside the subprocess (not passed
across process boundaries).

## New dependency

`igittigitt` added to `pyproject.toml`. Replaces the original plan to use `pathspec`.

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Add `igittigitt` dependency |
| `src/mcp_tools_py/main.py` | Add `--refactoring-timeout` CLI argument |
| `src/mcp_tools_py/server.py` | Add `refactoring_timeout` parameter to `CodeCheckerServer` and `create_server` |
| `src/mcp_tools_py/refactoring/__init__.py` | Accept `timeout` in `RefactoringTools.__init__`, pass to rope functions |
| `src/mcp_tools_py/refactoring/rope_tools.py` | `ropefolder=None`, gitignore filtering via `igittigitt`, `_run_with_timeout()` wrapper, `timeout` param on public functions |
| `tests/test_refactoring/test_rope_tools.py` | Tests for timeout, ropefolder, gitignore filtering |

## Files NOT Modified

| File | Reason |
|------|--------|
| `src/mcp_tools_py/refactoring/jedi_tools.py` | Jedi tools work fine, no changes needed |
| `src/mcp_tools_py/checker_tools.py` | Checker tools unrelated |

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Disable `.ropeproject/` cache + gitignore-aware filtering via `igittigitt` | `step_1.md` |
| 2 | Multiprocessing timeout wrapper + `--refactoring-timeout` CLI plumbing | `step_2.md` |
