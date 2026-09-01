# Step 5 — lint-imports

`run_lint_imports_check_impl` currently reports
`"ERROR: lint-imports output could not be parsed"` on a timeout — the right severity for
the wrong cause. It reports the same wrong cause when `execute_command` sets
`execution_error` without `timed_out` — the `FileNotFoundError` / `PermissionError` /
`OSError` path, which also yields empty stdout and stderr, so `_parse_summary` finds
nothing and `_classify_state` returns `ERROR`. Both branches are fixed here.

## WHERE

- `src/mcp_tools_py/code_checker_lint_imports/runners.py`
- `src/mcp_tools_py/checker_tools/lint_imports_tool.py`
- `tests/test_code_checker_lint_imports/test_runners.py`

## WHAT

```python
def run_lint_imports_check_impl(
    lint_imports_binary: str,
    project_dir: str,
    extra_args: list[str] | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> str:
```

## HOW

- `from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT`.
  `code_checker_lint_imports → utils` is already declared in `tach.toml`.
- Pass `timeout_seconds=timeout_seconds` to `execute_command`.
- Return **before** `_parse_summary` / `_classify_state` / `_format_report`, so the
  parsing path never sees empty output and never mislabels it.
- The module contract is that the first non-empty line is the state header; both new
  returns must keep that true. Return the header alone — do not prepend the `info_line`.
- Check `timed_out` **before** `execution_error`: `execute_command` sets both on a
  timeout, so testing `execution_error` first would shadow the timeout branch.
- In `lint_imports_tool.py`, inside the existing `try`, pass
  `server.resolve_timeout("lint-imports")` as the fourth argument to
  `run_lint_imports_check_impl(...)`. Note the hyphen: the config key is
  `lint-imports-timeout`.
- This tool reads no project config today, so a malformed `pyproject.toml` now fails it —
  that is the intended consequence recorded in the summary.

## ALGORITHM

```
result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)
if result.timed_out:
    return f"=== ERROR: lint-imports timed out after {timeout_seconds} seconds ==="
if result.execution_error:
    return f"=== ERROR: lint-imports failed to run: {result.execution_error} ==="
combined = ...   # unchanged from here on
```

## DATA

Return type unchanged (`str`). The `=== ... ===` framing matches
`_format_state_header`'s output shape, so a caller scanning the first non-empty line
still sees a state header — for both the timeout and the execution-error return.

## TESTS (write first)

In `tests/test_code_checker_lint_imports/test_runners.py`:
- timeout: `make_command_result(timed_out=True, execution_error="Process timed out after 5 seconds")`
  → first non-empty line contains `"ERROR"`, `"timed out"` and the number, and the result
  does **not** contain `"could not be parsed"`
- timeout with `extra_args=["--verbose"]` → still a single state-header line (the info
  line about stripped flags is not prepended)
- execution error: `make_command_result(execution_error="FileNotFoundError: lint-imports")`
  with `timed_out=False` → first non-empty line contains `"ERROR"` and the error text,
  and the result does **not** contain `"could not be parsed"`
- forwarding: explicit `timeout_seconds=45` reaches `execute_command`
- default: omitted → `120`

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_5.md`. Implement step 5 only.
>
> Write the tests first, setting `timed_out=True` **together with** a non-empty
> `execution_error` as the summary requires. Then add `timeout_seconds` to
> `run_lint_imports_check_impl`, forward it to `execute_command`, add the early
> `timed_out` return followed by an `execution_error` return — both before any parsing,
> so neither a killed nor a failed run is mislabelled
> `"ERROR: lint-imports output could not be parsed"` — and pass
> `server.resolve_timeout("lint-imports")` from `checker_tools/lint_imports_tool.py`.
> Then run `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n","auto"])` and `run_mypy_check`, and commit once.
