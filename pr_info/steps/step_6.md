# Step 6 — bandit

`run_bandit_check_impl` tests `execution_error` first, so its `timed_out` branch at
`runners.py:73-76` is unreachable dead code.

## WHERE

- `src/mcp_tools_py/code_checker_bandit/runners.py`
- `src/mcp_tools_py/checker_tools/bandit_tool.py`
- `tests/test_code_checker_bandit/test_runners.py`

## WHAT

```python
def run_bandit_check_impl(
    bandit_binary: str,
    project_dir: str,
    target_directories: list[str],
    extra_args: list[str] | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> BanditResult:
```

## HOW

- `from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT`.
  `code_checker_bandit → utils` is already declared in `tach.toml`.
- Pass `timeout_seconds=timeout_seconds` to `execute_command`.
- **Move** the existing `if result.timed_out:` block **above** the
  `if result.execution_error:` block, and make its message name the limit.
- In `bandit_tool.py`, inside the existing `try`, add
  `timeout_seconds=server.resolve_timeout("bandit")` to the
  `run_bandit_check_impl(...)` call.

## ALGORITHM

```
result = execute_command(cmd, cwd=project_dir, timeout_seconds=timeout_seconds)
if result.timed_out:
    return BanditResult(-1, [], [], error=f"timed out after {timeout_seconds} seconds")
if result.execution_error:
    ... unchanged ...
```

## DATA

`BanditResult(return_code=-1, messages=[], errors=[], error=...)` as today — only the
`error` text and the branch order change. `bandit_tool` renders it as
`f"bandit error: {result.error}"`.

## TESTS (write first)

In `tests/test_code_checker_bandit/test_runners.py`:
- **Fix the existing `test_timeout`.** It currently passes `make_command_result(timed_out=True)`
  with `execution_error=None` — a state `execute_command` never produces, which is why it
  passes today against the dead branch. Set both fields and assert the message names the
  seconds.
- forwarding: explicit `timeout_seconds=45` reaches `execute_command`
- default: omitted → `120`

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_6.md`. Implement step 6 only.
>
> Start by fixing the existing `test_timeout` in
> `tests/test_code_checker_bandit/test_runners.py` so it sets `timed_out=True` **together
> with** a non-empty `execution_error` and asserts the message names the limit — it
> should fail against the current dead branch. Then add `timeout_seconds` to
> `run_bandit_check_impl`, forward it to `execute_command`, move the `timed_out` branch
> above the `execution_error` branch, and pass `server.resolve_timeout("bandit")` from
> `checker_tools/bandit_tool.py`. Then run `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n","auto"])` and `run_mypy_check`, and commit once.
