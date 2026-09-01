# Step 3 — tach

`run_tach_check` currently returns `"tach check passed (no output)."` when killed by a
timeout: **a killed check reports green.** It reports the same false green when
`execute_command` sets `execution_error` without `timed_out` — the
`FileNotFoundError` / `PermissionError` / `OSError` path, which also yields empty
stdout and stderr. Both branches are fixed here; leaving one would keep a false pass in
the function this step already opens.

## WHERE

- `src/mcp_tools_py/code_checker_tach/runners.py`
- `src/mcp_tools_py/checker_tools/tach_tool.py`
- `tests/test_code_checker_tach/test_runners.py`
- `tests/test_checker_tools.py` — the strict `assert_called_once_with` at ~line 478

## WHAT

```python
def run_tach_check(
    tach_binary: str,
    project_dir: str,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> str:
```

## HOW

- `from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT` — the default
  keeps existing direct callers and tests working; the registrar always passes a resolved
  value. `code_checker_tach → utils` is already declared in `tach.toml`.
- Pass `timeout_seconds=timeout_seconds` to `execute_command`.
- In `tach_tool.py`, inside the existing `try`, add
  `timeout_seconds=server.resolve_timeout("tach")` to the `run_tach(...)` call. A
  `ValueError` from a malformed `pyproject.toml` is caught by the existing
  `except Exception` and returned as a message.
- Check `timed_out` **before** `execution_error`: `execute_command` sets both on a
  timeout, so testing `execution_error` first would shadow the timeout branch — the
  defect this issue exists to remove elsewhere.

## ALGORITHM

```
result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)
if result.timed_out:
    return f"tach check timed out after {timeout_seconds} seconds."
if result.execution_error:
    return f"tach check failed to run: {result.execution_error}"
... existing stdout/stderr combining unchanged ...
```

Both new branches go immediately after `execute_command`, before the output is combined.

## DATA

Return type unchanged (`str`). The two messages replace the false
`"tach check passed (no output)."`.

## TESTS (write first)

In `tests/test_code_checker_tach/test_runners.py`:
- timeout: `make_command_result(timed_out=True, execution_error="Process timed out after 5 seconds")`
  → result contains `"timed out"` and the configured number, and does **not** contain
  `"passed"`
- execution error: `make_command_result(execution_error="FileNotFoundError: tach")`
  with `timed_out=False` → result contains the error text and does **not** contain
  `"passed"`
- forwarding: `run_tach_check(binary, dir, timeout_seconds=45)` → the `execute_command`
  mock received `timeout_seconds=45`
- default: called without the argument → `execute_command` received `120`

In `tests/test_checker_tools.py`, extend the `mock_runner.assert_called_once_with(...)`
for tach with `timeout_seconds=120` (the fixture's `resolve_timeout` from step 2).

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_3.md`. Implement step 3 only.
>
> Write the tests first. Remember the summary's rule: a timeout test must set
> `timed_out=True` **together with** a non-empty `execution_error`, because
> `make_command_result` defaults `execution_error` to `None` and that state never occurs
> in production.
>
> Then add `timeout_seconds` to `run_tach_check`, forward it to `execute_command`, add
> the `timed_out` branch followed by an `execution_error` branch — a killed or failed
> tach run must never fall through to `"tach check passed (no output)."` — and pass
> `server.resolve_timeout("tach")` from
> `checker_tools/tach_tool.py`. Then run `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n","auto"])` and `run_mypy_check`, and commit once.
