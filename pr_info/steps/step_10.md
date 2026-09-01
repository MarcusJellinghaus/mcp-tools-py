# Step 10 — pytest (plus per-call `timeout_seconds`)

pytest is the one tool whose timeout is already a parameter, plumbed
`check_code_with_pytest` → `run_tests` → both `execute_command` calls. Only the MCP tool
surface and the branch order are missing.

`run_tests` raises `RuntimeError` on `execution_error` at `runners.py:225`, before the
`TimeoutError` at `:231-242` — so the `TimeoutError` is unreachable.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/runners.py`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `tests/test_code_checker/test_runners.py`
- `tests/test_server_params.py` — the strict `assert_called_once_with` at lines 74-85

## WHAT

```python
# pytest_tool.py — new MCP tool argument
def run_pytest_check(
    markers: Optional[List[str]] = None,
    extra_args: Optional[List[str]] = None,
    env_vars: Optional[Dict[str, str]] = None,
    timeout_seconds: Optional[int] = None,
) -> str: ...
```

`run_tests` and `check_code_with_pytest` keep their existing
`timeout_seconds: int = 300`. Do not change those signatures or defaults.

## HOW

- `runners.py`: **move** the `if subprocess_result.timed_out:` block **above** the
  `if subprocess_result.execution_error:` block at the main call site, so the
  `TimeoutError` wins over the `RuntimeError`.
- Include the limit in both timeout messages — the main one and the post-install retry at
  `:303`, which already checks `timed_out` first.
- `pytest_tool.py`: inside the existing `try`, add
  `timeout_seconds=server.resolve_timeout("pytest", timeout_seconds)` to the
  `check_code_with_pytest(...)` call. The existing `except Exception` returns a message,
  so an invalid value comes back as text.
- Docstring for the new argument, e.g.:
  *"Maximum seconds to wait for the test run. Overrides the configured limit for this
  call. Must be a positive integer. Defaults to `[tool.mcp-tools-py]` config, then
  `--check-timeout`, then 300."*
- Leave the 60s pytest-json-report pip install hardcoded — it does not run user code.
  When the plugin is missing, one tool call can therefore cost up to
  2× `pytest-timeout` + 60s.

## ALGORITHM

```
if subprocess_result.timed_out:
    detail = _build_error_detail(stdout, stderr)
    raise TimeoutError(f"Subprocess timed out after {timeout_seconds} seconds: {' '.join(command)}.{detail}")
if subprocess_result.execution_error:
    ... unchanged RuntimeError ...
```

Retry site: same wording pattern, keeping its existing "after installing
pytest-json-report" context.

## DATA

`TimeoutError` propagates out of `run_tests`; `check_code_with_pytest` turns it into the
result dict's `error`, which `_format_pytest_result_with_details` renders as
`"Error running pytest: ..."`.

## TESTS (write first)

`tests/test_code_checker/test_runners.py`:
- main-call timeout: `make_command_result(timed_out=True, execution_error="Process timed out after 5 seconds")`
  → `TimeoutError` (not `RuntimeError`), message names the seconds
- the existing retry-timeout test at ~line 586 already sets `execution_error=None` with
  `timed_out=True`; give it a non-empty `execution_error` and assert the message names
  the seconds
- the positional `mock_run_tests.assert_called_once_with(...)` at lines 221-233 keeps its
  `300,  # timeout_seconds` entry — `check_code_with_pytest`'s signature is unchanged.
  Confirm it still passes rather than editing it.

`tests/test_server_params.py`:
- **update** the `mock_check_pytest.assert_called_once_with(...)` at lines 74-85 to
  include `timeout_seconds=300` — the test builds a real `ToolServer` on a path with no
  `pyproject.toml`, so resolution yields pytest's built-in
- `run_pytest_check(timeout_seconds=900)` → `check_code_with_pytest` called with
  `timeout_seconds=900`

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_10.md`. Implement step 10 only.
>
> Write the tests first, setting `timed_out=True` **together with** a non-empty
> `execution_error` as the summary requires — the main-call test should currently raise
> `RuntimeError` and so fail. Then move the `timed_out` branch above the
> `execution_error` branch in `code_checker_pytest/runners.py`, name the limit in both
> timeout messages, and add the `timeout_seconds` MCP tool argument in
> `checker_tools/pytest_tool.py` resolving via
> `server.resolve_timeout("pytest", timeout_seconds)`.
>
> Do not change the signatures or defaults of `run_tests` or `check_code_with_pytest`,
> and leave the 60s pip install hardcoded. Then run `run_format_code`,
> `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])` and `run_mypy_check`,
> and commit once.
