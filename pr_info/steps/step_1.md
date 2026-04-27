# Step 1: Create `code_checker_tach` Subpackage + Unit Tests

## LLM Prompt
> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`, then implement step 1. Follow TDD: write the tests first, then the runner. Run `mcp__tools-py__run_pylint_check`, `run_pytest_check`, and `run_mypy_check` after the change; all must pass before commit.

## WHERE

Create:
- `src/mcp_tools_py/code_checker_tach/__init__.py`
- `src/mcp_tools_py/code_checker_tach/runners.py`
- `tests/test_code_checker_tach/__init__.py`
- `tests/test_code_checker_tach/test_runners.py`

## WHAT

```python
# src/mcp_tools_py/code_checker_tach/runners.py
def run_tach_check(tach_binary: str, project_dir: str) -> str:
    """Run `tach check --output json` and return status line + raw output."""
```

```python
# src/mcp_tools_py/code_checker_tach/__init__.py
"""Code checker package for running tach architecture boundary checks."""

from mcp_tools_py.code_checker_tach.runners import run_tach_check

__all__ = ["run_tach_check"]
```

(Module docstring mirrors `src/mcp_tools_py/code_checker_vulture/__init__.py`'s pattern.)

## HOW

- Use `mcp_tools_py.utils.subprocess_runner.execute_command` (same as vulture).
- No `@log_function_call` decorator on the runner itself (vulture's runner doesn't use one); logging happens at `checker_tools` layer in step 3.
- Tests mirror `tests/test_code_checker_vulture/test_runners.py`. Use `make_command_result` from `tests.conftest`.

## ALGORITHM

```
command = [tach_binary, "check", "--output", "json"]
result = execute_command(command, cwd=project_dir)
output = result.stdout
if result.stderr:
    output = output + "\n" + result.stderr if output else result.stderr
stripped = output.strip()
return f"tach check completed:\n{stripped}" if stripped else "tach check passed (no output)."
```

## DATA

- **Returns**: `str`
  - Success with output: `"tach check completed:\n{json}"`
  - Success with stderr only: `"tach check completed:\n{stderr}"`
  - Empty stdout + empty stderr: `"tach check passed (no output)."`

## Tests (write first)

In `tests/test_code_checker_tach/test_runners.py`, mock `execute_command` and cover:
1. `test_run_tach_success_returns_status_line_and_json` — stdout returned with `"tach check completed:"` prefix.
2. `test_run_tach_combines_stderr` — both stdout and stderr present → both appear in output.
3. `test_run_tach_stderr_only` — stderr but empty stdout → stderr appears in output.
4. `test_run_tach_empty_output_fallback` — empty stdout/stderr → returns `"tach check passed (no output)."`.
5. `test_run_tach_command_construction` — command is `[tach_binary, "check", "--output", "json"]`, `cwd` is project_dir.

Use `MODULE_PATH = "mcp_tools_py.code_checker_tach.runners"` and `@patch(f"{MODULE_PATH}.execute_command")`.

## Acceptance

- `mcp__tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])` — all pass.
- `run_pylint_check`, `run_mypy_check` — clean.
- One commit: tests + implementation.
