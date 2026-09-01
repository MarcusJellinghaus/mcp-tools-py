# Step 8 — mypy (plus per-call `timeout_seconds`)

The motivating case. `run_mypy_check` hardcodes `timeout_seconds=120` and tests
`execution_error` before `timed_out`, so the hand-written message at `runners.py:160`
never fires — the observed
`Mypy execution failed: Process timed out after 120 seconds` comes from the generic
`reporting.py` path instead.

Two hops: `mypy_tool` → `get_mypy_prompt` → `run_mypy_check`.

## WHERE

- `src/mcp_tools_py/code_checker_mypy/runners.py`
- `src/mcp_tools_py/code_checker_mypy/reporting.py` — `get_mypy_prompt` pass-through
- `src/mcp_tools_py/checker_tools/mypy_tool.py`
- `tests/test_error_transparency.py` — mypy runner section
- `tests/test_server_params.py` or `tests/test_checker_tools.py` — tool-argument wiring

## WHAT

```python
# runners.py
def run_mypy_check(..., config_file: str | None = None,
                   timeout_seconds: int = DEFAULT_CHECK_TIMEOUT) -> MypyResult: ...

# reporting.py
def get_mypy_prompt(..., cache_dir: str | None = None,
                    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT) -> str | None: ...

# mypy_tool.py — new MCP tool argument
def run_mypy_check(
    strict: bool = True,
    disable_error_codes: list[str] | None = None,
    target_directories: list[str] | None = None,
    follow_imports: str | None = None,
    cache_dir: str | None = None,
    timeout_seconds: int | None = None,
) -> str: ...
```

## HOW

- `from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT` in both
  `runners.py` and `reporting.py`. `code_checker_mypy → utils` is already declared.
- `runners.py`: replace the hardcoded `timeout_seconds=120` with the parameter.
- `runners.py`: insert `if result.timed_out:` **immediately before**
  `if result.execution_error:` — that is, after the `check_tool_missing_error` guard,
  which returns `None` on the empty stderr a timeout produces.
- Delete the now-superseded `timed_out` block that currently sits *after* the
  `execution_error` block; do not leave two.
- `reporting.py`: forward `timeout_seconds=timeout_seconds` to `run_mypy_check`.
- `mypy_tool.py`: resolve **inside** the existing `try`, as
  `timeout_seconds=server.resolve_timeout("mypy", timeout_seconds)`. This tool's
  `except` re-raises, so an invalid value surfaces as an MCP error carrying the
  `ValueError` message — intended.
- Docstring for the new argument, e.g.:
  *"Maximum seconds to wait for mypy. Overrides the configured limit for this call.
  Must be a positive integer. Defaults to `[tool.mcp-tools-py]` config, then
  `--check-timeout`, then 120."*

## ALGORITHM

```
result = execute_command(command, cwd=project_dir, timeout_seconds=timeout_seconds, env=env)
tool_error = check_tool_missing_error(...)      # unchanged, first
if tool_error: return MypyResult(...)
if result.timed_out:
    return MypyResult(1, [], error=f"Mypy execution timed out after {timeout_seconds} seconds")
if result.execution_error:
    ... unchanged ...
```

## DATA

`MypyResult(return_code=1, messages=[], error="Mypy execution timed out after N seconds")`.
`reporting.get_mypy_prompt` already prefixes `result.error` with
`"Mypy execution failed: "`, so the user-visible string becomes
`Mypy execution failed: Mypy execution timed out after 600 seconds`. That double prefix
is acceptable; do not restructure the reporting path in this step.

## TESTS (write first)

`tests/test_error_transparency.py`, mypy section:
- timeout: `make_command_result(timed_out=True, execution_error="Process timed out after 5 seconds")`
  → `result.error` contains `"timed out"` and the configured number, and does **not**
  contain the generic `execution_error` text
- forwarding: explicit `timeout_seconds=600` reaches `execute_command`
- default: omitted → `120`

Tool wiring:
- `run_mypy_check(timeout_seconds=900)` → `get_mypy_prompt` called with
  `timeout_seconds=900`
- `run_mypy_check()` with no server config → `get_mypy_prompt` called with
  `timeout_seconds=120`

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_8.md`. Implement step 8 only.
>
> Write the tests first, setting `timed_out=True` **together with** a non-empty
> `execution_error` as the summary requires — the runner test should fail against the
> current dead branch. Then add `timeout_seconds` to `run_mypy_check` (replacing the
> hardcoded 120) and to `get_mypy_prompt`, move the `timed_out` check above the
> `execution_error` check and delete the old one, and add the `timeout_seconds` MCP tool
> argument in `checker_tools/mypy_tool.py` resolving via
> `server.resolve_timeout("mypy", timeout_seconds)` inside the existing `try`. Document
> the new argument in the tool docstring. Then run `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n","auto"])` and `run_mypy_check`, and commit once.
