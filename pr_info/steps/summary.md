# Issue #121: Add lint-imports as MCP tool

## Summary

Add `run_lint_imports_check` as a new MCP tool alongside the existing pylint/pytest/mypy checkers. This ensures `lint-imports` always runs in the correct project virtual environment, avoiding the wrong-venv problem from #592.

## Architectural / Design Changes

### What changes

1. **`server.py` — `_check_tool_availability()`**: Add a file-existence check for the `lint-imports` binary in the venv. Unlike pylint/pytest/mypy which use `python -m <tool> --version`, lint-imports cannot be invoked via `python -m importlinter`, so we check for the binary file directly.

2. **`checker_tools.py` — `CheckerTools` class**: Add `_register_lint_imports()` method called from `register()`. The tool handler resolves the binary path, runs it via `execute_command()`, and returns raw stdout+stderr as-is (no parsing/formatting layer needed).

### What does NOT change

- No new modules or subpackages — lint-imports output is plain text, no models/parsers/reporters needed.
- No changes to `subprocess_runner.py`, `tach.toml`, or `.importlinter`.
- The existing 3 checkers are untouched.

### Design decisions

| Decision | Rationale |
|----------|-----------|
| File existence check (not subprocess) | `python -m importlinter` doesn't work; file check is faster with no side effects |
| Raw text pass-through | Output is already LLM-readable; no parsing needed |
| `cwd=project_dir` | So lint-imports finds `.importlinter` config |
| Binary path from `venv_path` | Platform-aware: `Scripts/lint-imports` (Windows) vs `bin/lint-imports` (Linux) |
| In `checker_tools.py` | Conceptually a checker; simple enough for the same module |

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/server.py` | Add `lint-imports` to `_check_tool_availability()` |
| `src/mcp_tools_py/checker_tools.py` | Add `_register_lint_imports()`, update `register()` |
| `tests/test_checker_tools.py` | Update registration count 3→4, add lint-imports formatting tests |
| `tests/test_tool_availability.py` | Add `lint-imports` to availability assertions, add short-circuit test |

## Files Created

None.

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Add lint-imports availability check to `server.py` + tests | `feat: add lint-imports availability check via file existence` |
| 2 | Add `run_lint_imports_check` tool to `checker_tools.py` + tests | `feat: add run_lint_imports_check MCP tool` |
