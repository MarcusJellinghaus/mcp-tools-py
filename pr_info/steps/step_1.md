# Step 1: Shared formatter used by `run_tach_check`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, `pr_info/steps/step_1.md`. Implement this step only, tests first. Run the listed checks, fix anything they report, then make one commit.

## WHERE

- `tests/test_code_checker_tach/test_runners.py`
- `src/mcp_tools_py/code_checker_tach/runners.py`
- `src/mcp_tools_py/checker_tools/tach_tool.py`

## WHAT

```python
def format_tach_result(result: CommandResult) -> str: ...
```

`run_tach_check` keeps its signature.

## HOW

- In `runners.py`, import `CommandResult` alongside `execute_command` from `mcp_tools_py.utils.subprocess_runner`.
- `run_tach_check` keeps its timeout and execution-error branches unchanged, then returns `format_tach_result(result)`. The merge and strip code moves into the formatter unchanged.
- Do not add the formatter to `code_checker_tach/__init__.py`. Step 2 imports it from `.runners`, like the other checkers in `toolkit_checks.py`.
- Leave the log line at `tach_tool.py:43` alone.

## ALGORITHM

```python
output = result.stdout
if result.stderr:
    output = output + "\n" + result.stderr if output else result.stderr
stripped = output.strip()
if result.return_code == 0:
    return f"tach check passed:\n{stripped}" if stripped else "tach check passed (no output)."
return f"tach check failed:\n{stripped}" if stripped else f"tach check failed (exit code {result.return_code}, no output)."
```

## DATA

The formatter returns a `str`, as listed in the summary's table.

Docstrings:

- `format_tach_result`: returns a status line from tach's exit code, followed by its combined stdout and stderr when there is any.
- `run_tach_check`, `Returns:` section: the formatter's text, or a message when tach timed out or failed to run.
- `tach_tool.py` `run_tach_check`, `Returns:` section: a status line saying whether `tach check` passed or failed, by its exit code, followed by tach's output. The output is JSON, or plain text when the config fails to load. Remove the promise of raw JSON.

## TDD

Write this first and confirm it fails. In `test_runners.py`, replace these four tests with one parametrized test:

- `test_run_tach_success_returns_status_line_and_json`
- `test_run_tach_combines_stderr`
- `test_run_tach_stderr_only`
- `test_run_tach_empty_output_fallback`

Call `run_tach_check` with `execute_command` patched, and assert the whole reply:

| `return_code` | `stdout` | `stderr` | Expected reply |
|---|---|---|---|
| 0 | `'{"errors": []}\n'` | `""` | `'tach check passed:\n{"errors": []}'` |
| 0 | `'{"errors": []}'` | `"warning: deprecated"` | `'tach check passed:\n{"errors": []}\nwarning: deprecated'` |
| 0 | `""` | `""` | `"tach check passed (no output)."` |
| 1 | `'{"errors": []}'` | `""` | `'tach check failed:\n{"errors": []}'` |
| 1 | `""` | `"error: bad config"` | `"tach check failed:\nerror: bad config"` |
| 1 | `""` | `""` | `"tach check failed (exit code 1, no output)."` |

Add `import pytest`. Keep the other tests in the file unchanged. No separate tests for the formatter: this table exercises it through the runner.

## Checks

- `run_pytest_check` with `extra_args=["-n", "auto", "-m", "not integration"]`
- `run_pylint_check`
- `run_mypy_check`
- `run_format_code`

## Commit

`fix(code_checker_tach): base status line on tach's exit code`
