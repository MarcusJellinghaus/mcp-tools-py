# Step 7 — ruff (three invocations)

ruff is one program behind two MCP tools, and `run_ruff_fix` spends its budget twice: a
pre-check call, then the apply call. All three sites test `execution_error` before
`timed_out`, so all three `timed_out` branches are dead.

## WHERE

- `src/mcp_tools_py/code_checker_ruff/runners.py` — three `execute_command` calls
- `src/mcp_tools_py/checker_tools/ruff_check_tool.py`
- `src/mcp_tools_py/checker_tools/ruff_fix_tool.py`
- `tests/test_code_checker_ruff/test_runners.py`

## WHAT

```python
def run_ruff_check_impl(
    ruff_binary: str,
    project_dir: str,
    target_directories: list[str],
    select: list[str] | None = None,
    extra_args: list[str] | None = None,
    max_issues: int = 1,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> str:


def run_ruff_fix_impl(
    ruff_binary: str,
    project_dir: str,
    target_directories: list[str],
    select: list[str] | None = None,
    extra_args: list[str] | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> str:
```

## HOW

- `from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT`.
  `code_checker_ruff → utils` is already declared in `tach.toml`.
- Pass `timeout_seconds=timeout_seconds` to **all three** `execute_command` calls: the
  check call, the fix pre-check call, and the fix apply call.
- **Move** each `if ....timed_out:` block above its `if ....execution_error:` block, and
  make each message name the limit.
- Both registrars resolve the same key: `server.resolve_timeout("ruff")`, inside their
  existing `try` blocks.
- One key bounds one *run*, so `run_ruff_fix` may legitimately spend up to
  2× `ruff-timeout`. Do not halve the value — the number in the config file must be the
  number in effect.

## ALGORITHM

At each of the three sites:

```
result = execute_command(cmd, cwd=project_dir, timeout_seconds=timeout_seconds)
if result.timed_out:
    return f"Ruff timed out after {timeout_seconds} seconds."       # fix apply site: "Ruff fix timed out after ..."
if result.execution_error:
    ... unchanged ...
```

## DATA

Return type unchanged (`str`). Only the message text and branch order change.

## TESTS (write first)

In `tests/test_code_checker_ruff/test_runners.py`:
- **Fix both existing `test_timeout` tests** (check and fix). They pass
  `make_command_result(timed_out=True)` with `execution_error=None` — a state
  `execute_command` never produces, which is why they pass today against dead branches.
  Set both fields and assert the message names the seconds.
- fix-apply timeout: first call returns fixable messages, second call returns a timeout →
  message contains `"fix"` and the seconds
- forwarding: `run_ruff_fix_impl(..., timeout_seconds=45)` with fixable findings → **both**
  `execute_command` calls received `timeout_seconds=45`
- default: omitted → `120`

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_7.md`. Implement step 7 only.
>
> Start by fixing the two existing `test_timeout` tests in
> `tests/test_code_checker_ruff/test_runners.py` so each sets `timed_out=True` **together
> with** a non-empty `execution_error` and asserts the message names the limit — they
> should fail against the current dead branches. Then add `timeout_seconds` to both impl
> functions, forward it to all three `execute_command` calls, move each `timed_out` branch
> above its `execution_error` branch, and pass `server.resolve_timeout("ruff")` from both
> `checker_tools/ruff_check_tool.py` and `checker_tools/ruff_fix_tool.py`. Then run
> `run_format_code`, `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])` and
> `run_mypy_check`, and commit once.
