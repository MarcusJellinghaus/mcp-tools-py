# Step 11 — black and isort

One MCP tool running two programs, so two separate keys: `black-timeout` and
`isort-timeout`. Both runners currently return `success=False` with empty output on a
timeout — no reason given. They give the same reasonless failure when `execute_command`
sets `execution_error` without `timed_out` (the `FileNotFoundError` /
`PermissionError` / `OSError` path, also empty stdout and stderr). Both branches are
fixed here.

black and isort are one step because the change is coupled: `formatter/runner.py`
dispatches both through a single positional signature
`runner(python_executable, target_dirs, project_root, check_only)`, so separating the two
budgets requires both runners to accept the new argument at once.

## WHERE

- `src/mcp_tools_py/formatter/black_runner.py`
- `src/mcp_tools_py/formatter/isort_runner.py`
- `src/mcp_tools_py/formatter/runner.py`
- `src/mcp_tools_py/formatter/formatter_tools.py`
- `tests/test_black_runner.py`, `tests/test_isort_runner.py`,
  `tests/test_formatter_runner.py`, `tests/test_formatter_tools.py`

## WHAT

```python
def run_black(python_executable: str, target_dirs: list[str], project_dir: str,
              check_only: bool = False,
              timeout_seconds: int = DEFAULT_CHECK_TIMEOUT) -> FormatterResult: ...

def run_isort(python_executable: str, target_dirs: list[str], project_dir: str,
              check_only: bool = False,
              timeout_seconds: int = DEFAULT_CHECK_TIMEOUT) -> FormatterResult: ...

def run_format_code(python_executable: str, project_root: Path, target_dirs: list[str],
                    steps: list[str] | None = None, check_only: bool = False,
                    timeouts: dict[str, int] | None = None) -> dict[str, FormatterResult]: ...
```

## HOW

- `from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT` in all three
  runner files. `formatter → utils` is already declared in `tach.toml`.
- Both runners take `timeout_seconds` as the **fifth positional** parameter so the single
  `_STEP_RUNNERS` dispatch keeps working with one shared call shape.
- `runner.py` dispatch becomes:
  `runner(python_executable, target_dirs, str(project_root), check_only, (timeouts or {}).get(step, DEFAULT_CHECK_TIMEOUT))`
- `formatter_tools.py` resolves both keys unconditionally into a literal dict:
  ```python
  timeouts = {
      "isort": self._server.resolve_timeout("isort"),
      "black": self._server.resolve_timeout("black"),
  }
  ```
  A dict comprehension over `resolved_steps` would pass a plain `str` where `ToolName`
  is required and fail mypy strict; two literal calls avoid a `cast`. The extra TOML read
  is negligible — this tool already reads `pyproject.toml` twice
  (`resolve_target_directories`, `check_line_length_conflicts`).
- Put the resolution inside the existing `try` that already returns `f"Error: {exc}"` on
  `ValueError`, so a malformed `pyproject.toml` surfaces as a message.
- A single `run_format_code` call may therefore spend up to
  `black-timeout + isort-timeout`. Do not split one budget across two programs.

## ALGORITHM

In each runner, after `execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)`:

```
if result.timed_out:
    return FormatterResult(
        output=f"black timed out after {timeout_seconds} seconds.",   # "isort ..." in isort_runner
        success=False,
        files_changed=[],
    )
if result.execution_error:
    return FormatterResult(
        output=f"black failed to run: {result.execution_error}",      # "isort ..." in isort_runner
        success=False,
        files_changed=[],
    )
... existing stdout/stderr combining unchanged ...
```

Check `timed_out` **before** `execution_error`: `execute_command` sets both on a timeout,
so testing `execution_error` first would shadow the timeout branch.

Both branches return before `_parse_isort_unparsable_files`, so neither a killed nor a
failed run is misreported as an unparsable-file failure.

## DATA

`FormatterResult(output=<timeout or execution-error message>, success=False, files_changed=[])`;
`unparsable_files` keeps its `default_factory=list`. `_format_results` renders the output
under the step's `## <step>` heading, and the existing fail-fast logic still stops the
sequence when `check_only` is False.

## TESTS (write first)

`tests/test_black_runner.py` and `tests/test_isort_runner.py`:
- timeout: `make_command_result(timed_out=True, execution_error="Process timed out after 5 seconds")`
  → `success is False`, `output` contains `"timed out"` and the number,
  `files_changed == []`
- execution error: `make_command_result(execution_error="FileNotFoundError: black")`
  with `timed_out=False` → `success is False` and `output` contains the error text, not
  an empty string
- forwarding: explicit `timeout_seconds=45` reaches `execute_command`
- default: omitted → `120`

`tests/test_formatter_runner.py`:
- `run_format_code(..., timeouts={"isort": 30, "black": 90})` → each step runner received
  its own value
- `timeouts=None` → both received `120`

`tests/test_formatter_tools.py`:
- `run_format_code()` → `_run_format_code` called with `timeouts={"isort": 120, "black": 120}`
  (from the step-2 fixture)

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_11.md`. Implement step 11 only.
>
> Write the tests first, setting `timed_out=True` **together with** a non-empty
> `execution_error` as the summary requires. Then add `timeout_seconds` as the fifth
> positional parameter of `run_black` and `run_isort` with the `timed_out` branch
> followed by an `execution_error` branch — neither a killed nor a failed run may return
> `success=False` with empty output — add the
> `timeouts` mapping to `formatter/runner.py` with a per-step lookup at the dispatch, and
> resolve both `"isort"` and `"black"` in `formatter/formatter_tools.py` inside its
> existing `try`.
>
> Keep the two budgets separate — do not split or halve a single configured value. Then
> run `run_format_code`, `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])`
> and `run_mypy_check`, and commit once.
