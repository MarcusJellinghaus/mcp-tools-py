# Step 2: `_run_tach` uses the shared formatter

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, `pr_info/steps/step_2.md`. Implement this step only, tests first. Run the listed checks, fix anything they report, then make one commit.

## Precondition

`format_tach_result` exists in `src/mcp_tools_py/code_checker_tach/runners.py` (step 1). If it does not, write one line to `pr_info/.blocked.txt` and stop.

## WHERE

- `tests/test_toolkit_check.py`
- `src/mcp_tools_py/toolkit_checks.py`

## WHAT

No new functions. `_run_tach(context: ToolContext, depth: str) -> ActionResult` keeps its signature, and now calls `format_tach_result`.

## HOW

- Add to the imports in `toolkit_checks.py`, between the pylint and vulture imports:
  `from mcp_tools_py.code_checker_tach.runners import format_tach_result`
- Remove the merge, strip and `message` block above the `return_code == 0` check.
- Keep `_run_tach`'s own `execute_command` call. Do not route it through `run_tach_check`.
- Keep `status`, `summary`, `key` and `fix_text=message` as they are.

## ALGORITHM

```python
# timeout and execution-error branches unchanged
if result.return_code == 0:
    return ActionResult(status="ok", summary="tach found no issues.")

message = format_tach_result(result)
finding = Finding(key=f"tach|{depth}", message=message)
# ActionResult(status="findings", ...) unchanged
```

## DATA

`ActionResult` has the same shape. On a non-zero exit, `findings[0].message` holds the formatter's `tach check failed` text.

Replace the first paragraph of the `_run_tach` docstring after its summary line with:

> `code_checker_tach.runners.run_tach_check` returns only text, so this builds and runs the same command itself to read the return code, and shares that runner's `format_tach_result` for the finding's message. tach's output has no stable per-location key, so a finding is reported once, keyed `tach|{depth}`.

The `Returns:` section stays.

## TDD

Write this first and confirm it fails. In `tests/test_toolkit_check.py`, parametrize `test_tach_violation_is_degraded_finding` over `(stdout, expected_message)`:

| `stdout` | `expected_message` |
|---|---|
| `'{"errors": []}'` | `'tach check failed:\n{"errors": []}'` |
| `""` | `"tach check failed (exit code 1, no output)."` |

- Both cases use `return_code=1`.
- Keep the existing assertions on `status`, `len(findings)` and `key`.
- Add `assert result.findings[0].message == expected_message`.
- Do not compare `fix_text` to the message: `_merge` rebuilds it with a leading `- `.

## Checks

- `run_pytest_check` with `extra_args=["-n", "auto", "-m", "not integration"]`
- `run_pylint_check`
- `run_mypy_check`
- `run_lint_imports_check`
- `run_tach_check`
- `run_format_code`

This step adds an import edge from `toolkit_checks` to `code_checker_tach`, so `run_lint_imports_check` and `run_tach_check` must pass as well.

## Commit

`fix(toolkit_checks): share tach status text with the runner`
