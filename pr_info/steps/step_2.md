# Step 2: Create `code_checker_vulture/` runner module + tests

> **Context**: See `pr_info/steps/summary.md` for full issue context and architecture.

## Goal

Extract vulture subprocess logic from `checker_tools.py` into a new `code_checker_vulture/runners.py` module. Update `tach.toml` with the new module boundary. Do NOT yet change `checker_tools.py` to call it — that happens in Step 3.

## WHERE

- `tests/test_code_checker_vulture/__init__.py` — create (empty)
- `tests/test_code_checker_vulture/test_runners.py` — create tests (TDD: tests first)
- `src/mcp_tools_py/code_checker_vulture/__init__.py` — create (empty or re-export)
- `src/mcp_tools_py/code_checker_vulture/runners.py` — create runner
- `tach.toml` — add module + dependency

## WHAT

### Function signature

```python
def run_vulture_check(
    vulture_binary: str,
    project_dir: str,
    target_directories: list[str],
    min_confidence: int = 60,
    extra_args: list[str] | None = None,
    whitelist_path: str | None = None,
) -> str:
```

**Returns**: Raw vulture output string (stdout + stderr combined), or error message.

### `__init__.py` re-export

```python
from mcp_tools_py.code_checker_vulture.runners import run_vulture_check
```

## HOW

- Uses `execute_command` from `utils.subprocess_runner` (same as current inline code)
- `whitelist_path` is an optional absolute path — appended to command paths if provided and exists
- `target_directories` is always explicit (never `None`) — resolution happens in caller

## ALGORITHM

```
paths = list(target_directories)
if whitelist_path and os.path.exists(whitelist_path):
    paths.append(whitelist_path)
command = [vulture_binary] + paths + ["--min-confidence", str(min_confidence)] + (extra_args or [])
result = execute_command(command, cwd=project_dir)
output = combine stdout + stderr
return output.strip() or "vulture produced no output."
```

## DATA

- **Input**: binary path, project dir, directories, confidence, extra args, whitelist path
- **Output**: `str` — raw combined output
- Uses `CommandResult` from `utils.subprocess_runner` internally

## `tach.toml` changes

Add new module entry:
```toml
[[modules]]
path = "mcp_tools_py.code_checker_vulture"
layer = "tool_implementation"
depends_on = [
    { path = "mcp_tools_py.utils" },
    { path = "mcp_tools_py.log_utils" }
]
```

Add dependency in `checker_tools` module:
```toml
{ path = "mcp_tools_py.code_checker_vulture" }
```

## Tests to write (in `tests/test_code_checker_vulture/test_runners.py`)

1. **`test_run_vulture_success`** — mock `execute_command` returning stdout, verify output returned
2. **`test_run_vulture_combines_stderr`** — mock with both stdout and stderr, verify combined output
3. **`test_run_vulture_no_output`** — mock empty output, verify "vulture produced no output." returned
4. **`test_run_vulture_includes_whitelist`** — provide `whitelist_path` to existing file, verify it's in command
5. **`test_run_vulture_skips_missing_whitelist`** — provide `whitelist_path` to non-existent file, verify it's NOT in command
6. **`test_run_vulture_passes_min_confidence`** — verify `--min-confidence` and value in command
7. **`test_run_vulture_passes_extra_args`** — verify extra args appended to command

All tests use `@patch` on `execute_command` with `make_command_result` from `tests.conftest`.

## Commit

```
refactor: extract vulture runner into code_checker_vulture module
```

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_2.md for full context.

Implement Step 2: Create the code_checker_vulture runner module.

1. First, create test files: tests/test_code_checker_vulture/__init__.py and tests/test_code_checker_vulture/test_runners.py
2. Then create source files: src/mcp_tools_py/code_checker_vulture/__init__.py and src/mcp_tools_py/code_checker_vulture/runners.py
3. Update tach.toml with the new module boundary and dependency
4. Run all three quality checks (pylint, mypy, pytest) and fix any issues
5. Commit with message: "refactor: extract vulture runner into code_checker_vulture module"

Do NOT modify checker_tools.py in this step — that's Step 3.
Use MCP tools for all file operations and quality checks per CLAUDE.md.
```
