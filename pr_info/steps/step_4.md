# Step 4 — vulture

`run_vulture_check` currently returns `"vulture produced no output."` when killed by a
timeout, which reads as "no dead code found" — **also a false pass.**

## WHERE

- `src/mcp_tools_py/code_checker_vulture/runners.py`
- `src/mcp_tools_py/checker_tools/vulture_tool.py`
- `tests/test_code_checker_vulture/test_runners.py`
- `tests/test_checker_tools.py` — any strict `assert_called_once_with` for the vulture runner

## WHAT

```python
def run_vulture_check(
    vulture_binary: str,
    project_dir: str,
    target_directories: list[str],
    min_confidence: int = 60,
    extra_args: list[str] | None = None,
    whitelist_path: str | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> str:
```

`timeout_seconds` goes last so no existing positional call breaks.

## HOW

- `from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT`.
  `code_checker_vulture → utils` is already declared in `tach.toml`.
- Pass `timeout_seconds=timeout_seconds` to `execute_command`.
- In `vulture_tool.py`, inside the existing `try`, add
  `timeout_seconds=server.resolve_timeout("vulture")` to the `run_vulture(...)` call.
- Timeouts only — do not add `execution_error` handling.

## ALGORITHM

```
result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds)
if result.timed_out:
    return f"vulture timed out after {timeout_seconds} seconds."
... existing stdout/stderr combining unchanged ...
```

## DATA

Return type unchanged (`str`). The timeout message replaces the false
`"vulture produced no output."`.

## TESTS (write first)

In `tests/test_code_checker_vulture/test_runners.py`:
- timeout: `make_command_result(timed_out=True, execution_error="Process timed out after 5 seconds")`
  → result contains `"timed out"` and the number, and does **not** contain
  `"produced no output"`
- forwarding: explicit `timeout_seconds=45` reaches `execute_command`
- default: omitted → `120`

Update the vulture assertion in `tests/test_checker_tools.py` if it pins the full kwargs.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_4.md`. Implement step 4 only.
>
> Write the tests first, setting `timed_out=True` **together with** a non-empty
> `execution_error` as the summary requires. Then add `timeout_seconds` to
> `run_vulture_check`, forward it to `execute_command`, add the `timed_out` branch, and
> pass `server.resolve_timeout("vulture")` from `checker_tools/vulture_tool.py`. Then run
> `run_format_code`, `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])` and
> `run_mypy_check`, and commit once.
