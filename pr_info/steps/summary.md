# Issue #154: Parallelize tool availability checks at server startup

## Problem
Server startup takes ~4.3s (cold). The main bottleneck is `_check_tool_availability()` in `server.py`, which runs 5 sequential `execute_command` subprocess calls (~3.2s total). Parallelizing these independent checks should reduce them to ~0.8s (the slowest single check).

## Architectural / Design Changes

### Before
`_check_tool_availability()` iterates over `["pytest", "pylint", "mypy", "black", "isort"]` in a sequential `for` loop, calling `execute_command()` for each. Total wall time = sum of all checks.

### After
The same 5 `execute_command()` calls are submitted to a `concurrent.futures.ThreadPoolExecutor` and gathered via `as_completed()`. Total wall time = max of all checks (~0.8s instead of ~3.2s).

### What does NOT change
- `subprocess_runner.py` — no modifications. `execute_command` is already thread-safe (independent subprocesses, no shared state).
- lint-imports and vulture checks — remain sequential after the parallel block (they use `os.path.exists`, already negligible).
- All existing tests — mocks use `side_effect` matching on command content, not call order.
- Tool registration, `_resolve_python_executable()`, `create_server()` — untouched.

### Key design decisions
- **Pattern:** `executor.submit()` + `as_completed()` per the issue spec.
- **Max workers:** Omitted — Python default (`min(32, cpu_count+4)`) is sufficient for 5 tasks.
- **Logging:** Per-tool timing via existing `CommandResult.execution_time_ms` (already measured inside `execute_command`). No additional timing code.
- **Import:** Module-level `from concurrent.futures import ThreadPoolExecutor, as_completed` (stdlib, no cost).

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/server.py` | Add import, refactor `_check_tool_availability()` to use ThreadPoolExecutor |
| `tests/test_tool_availability.py` | Add one new test verifying parallel execution produces correct results |

No new files or modules are created.

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Add new test + parallelize `_check_tool_availability()` | `perf: parallelize tool availability checks at startup (#154)` |
