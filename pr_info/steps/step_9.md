# Step 9 — pylint

`get_pylint_results` hardcodes `timeout_seconds=120` and tests `execution_error` before
`timed_out`, so its message at `runners.py:128` is dead.

No new MCP tool argument — the issue grants a per-call `timeout_seconds` to
`run_pytest_check` and `run_mypy_check` only.

Two hops: `pylint_tool` → `get_pylint_prompt` → `get_pylint_results`.

## WHERE

- `src/mcp_tools_py/code_checker_pylint/runners.py`
- `src/mcp_tools_py/code_checker_pylint/reporting.py` — `get_pylint_prompt` pass-through
- `src/mcp_tools_py/checker_tools/pylint_tool.py`
- `tests/test_error_transparency.py` — pylint runner section

## WHAT

```python
# runners.py
def get_pylint_results(
    project_dir: str,
    python_executable: str,
    extra_args: List[str] | None = None,
    target_directories: List[str] | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> PylintResult: ...

# reporting.py
def get_pylint_prompt(..., max_issues: int = 1,
                      timeout_seconds: int = DEFAULT_CHECK_TIMEOUT) -> Optional[str]: ...
```

## HOW

- `from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT` in both files.
  `code_checker_pylint → utils` is already declared.
- `runners.py`: replace the hardcoded `timeout_seconds=120` with the parameter.
- `runners.py`: insert `if subprocess_result.timed_out:` **immediately before** the
  `if subprocess_result.execution_error:` block. Note that pylint's tool-missing check
  lives *inside* that block, so the new branch must precede the whole block; on a timeout
  stderr is empty and the tool-missing check would return `None` anyway.
- Delete the now-superseded `timed_out` block that currently follows it.
- `reporting.py`: forward `timeout_seconds=timeout_seconds` to `get_pylint_results`.
- `pylint_tool.py`: resolve **before** the existing `try`, next to the
  `resolve_target_directories` call that already returns its failure as text:

  ```python
  try:
      resolved_timeout = server.resolve_timeout("pylint")
  except ValueError as exc:
      return f"Error: {exc}"
  ```

  Not inside the main `try` — that one ends in `except Exception: ... raise`, so a
  `ValueError` from an invalid `pylint-timeout` or a malformed `pyproject.toml` would
  escape as an MCP protocol error while every other checker returns text. Same shape as
  `mypy_tool` in step 8. The main `try` keeps re-raising real pylint failures, unchanged.
  Inside it, pass `timeout_seconds=resolved_timeout` to `get_pylint_prompt(...)`.

## ALGORITHM

```
subprocess_result = execute_command(pylint_command, cwd=project_dir, timeout_seconds=timeout_seconds)
if subprocess_result.timed_out:
    return PylintResult(1, [], error=f"timed out after {timeout_seconds} seconds", raw_output=None)
if subprocess_result.execution_error:
    ... unchanged (tool-missing check stays inside) ...
```

## DATA

`PylintResult(return_code=1, messages=[], error="timed out after N seconds", raw_output=None)`.
`reporting.py:235` already returns `f"Pylint analysis failed: {pylint_results.error}"`,
so the user-visible string reads `Pylint analysis failed: timed out after 600 seconds`.
The runner text carries no second "Pylint" prefix. Same shape as mypy in step 8.

## TESTS (write first)

`tests/test_error_transparency.py`, pylint section (it already patches
`code_checker_pylint.runners.execute_command`):
- timeout: `make_command_result(timed_out=True, execution_error="Process timed out after 5 seconds")`
  → `result.error` contains `"timed out"` and the configured number, and does **not**
  contain the generic `execution_error` text
- forwarding: explicit `timeout_seconds=600` reaches `execute_command`
- default: omitted → `120`

Tool wiring:
- `run_pylint_check()` → `get_pylint_prompt` called with `timeout_seconds=120` (from the
  step-2 fixture)
- a `resolve_timeout` that raises `ValueError` → `run_pylint_check()` **returns** a
  message containing the error text; it does not raise, and `get_pylint_prompt` is never
  called

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_9.md`. Implement step 9 only.
>
> Write the tests first, setting `timed_out=True` **together with** a non-empty
> `execution_error` as the summary requires — the runner test should fail against the
> current dead branch. Then add `timeout_seconds` to `get_pylint_results` (replacing the
> hardcoded 120) and to `get_pylint_prompt`, move the `timed_out` check above the whole
> `execution_error` block and delete the old one, keep the runner's timeout text free of
> a second "Pylint" prefix since `get_pylint_prompt` already adds one, and resolve
> `server.resolve_timeout("pylint")` in `checker_tools/pylint_tool.py` **before** the
> existing `try`, with its own `except ValueError` returning the message — that `try`
> ends in `raise`, so resolving inside it would turn an invalid `pylint-timeout` into an
> MCP protocol error instead of text. Same shape as `mypy_tool` in step 8.
>
> Do **not** add a `timeout_seconds` MCP tool argument — only pytest and mypy get one.
> Then run `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n","auto"])` and `run_mypy_check`, and commit once.
