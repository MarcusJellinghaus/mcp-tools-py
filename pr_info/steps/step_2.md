# Step 2: `check_code_with_pytest` returns `verdict`, and test dicts are migrated

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_2.md`. Update the `check_code_with_pytest` tests first, then `runners.py`. Then add `tests/_pytest_results.py` and migrate every hand-built result dict from `success` to `verdict`. Give the three consumers only the minimal reads listed below; their real logic comes in steps 3–5. Run pylint, mypy and pytest (`-n auto`), make sure all of them pass, run `run_format_code`, then make one commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/runners.py`: `check_code_with_pytest` only.
- New file `tests/_pytest_results.py`, containing the test helper.
- Minimal reads in `checker_tools/__init__.py`, `toolkit.py` and `checker_tools/pytest_tool.py`.
- Test files to migrate. Search `tests/` for `"success"` and update every hit:
  - `tests/test_checker_tools_formatting.py`
  - `tests/test_final_validation.py`
  - `tests/test_server_params.py`, including `_pytest_results()` around line 839 and the mock around line 999.
  - `tests/test_code_checker/test_runners.py`
  - `tests/test_code_checker_pytest/test_reporting.py`
  - `tests/test_code_checker_pytest/test_runners.py`
  - `tests/test_tool_availability/test_handler_short_circuit.py`

## WHAT

`runners.py`:

```python
from mcp_tools_py.code_checker_pytest.verdict import RunStatus, RunVerdict, classify_run
```

1. Delete the `error_info` block.
2. Success path: return `{"verdict": classify_run(test_results), "summary": ..., "summary_text": ..., "failed_tests_prompt": ..., "test_results": test_results}`.
3. `except` path: return `{"verdict": RunVerdict(RunStatus.ERROR, [str(e)], 0)}`.
4. Docstring Returns block: replace `success` and `error_info` with `verdict: RunVerdict (status, problems, exit_code); ERROR on any exception, with the message in problems`.

`tests/_pytest_results.py`:

```python
def make_pytest_results(
    status: RunStatus = RunStatus.PASSED,
    problems: list[str] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    """Hand-built check_code_with_pytest result; summary_text defaults to ''."""
    return {"verdict": RunVerdict(status, problems or [], 0), "summary_text": "", **fields}
```

`summary_text` defaults to `""` because it is falsy, so the formatter's existing `All N tests passed` fallback still fires, for example in `test_handler_short_circuit`.

How the old dicts map to the helper:

| Old dict | New call |
|---|---|
| `success: True`, no failures | `make_pytest_results(summary=..., ...)` |
| `success: True`, `failed > 0` or `error > 0` | `make_pytest_results(RunStatus.FAILED, summary=..., ...)` |
| `{"success": False, "error": msg}` | `make_pytest_results(RunStatus.ERROR, [msg])` |

## Minimal consumer reads

These keep today's behaviour. Steps 3–5 replace them.

- **Formatter:** replace the `if not test_results["success"]` guard with this, leaving the rest unchanged:
  ```python
  verdict = test_results["verdict"]
  if test_results.get("test_results") is None and verdict.status is RunStatus.ERROR:
      return f"Error running pytest: {'; '.join(verdict.problems) or 'Unknown error'}"
  ```
- **`toolkit._run_test`:** replace the `if not result["success"]` block with this:
  ```python
  verdict = result["verdict"]
  if "test_results" not in result:
      message = "\n".join(verdict.problems)
      return ActionResult(status="skipped" if "No Tests Found" in message else "error", summary=message)
  ```
- **`pytest_tool`:**
  - Replace `not test_results.get("success")` with `"test_results" not in test_results`.
  - Branch the log on that same condition.
  - Log `"; ".join(verdict.problems)` where it used to log `error`.

## ALGORITHM

There is no new logic in this step. It is a data-shape migration.

## DATA

`check_code_with_pytest` returns `dict[str, Any]` in one of two shapes:

- Success path: the keys `verdict`, `summary`, `summary_text`, `failed_tests_prompt` and `test_results`.
- Exception path: only `verdict`.

## Tests (updated first)

In `tests/test_code_checker/test_runners.py`:

- Passing run: `result["verdict"].status is RunStatus.PASSED` and `"success" not in result`.
- Failing run: `status is RunStatus.FAILED`.
- Exception: `result == {"verdict": RunVerdict(RunStatus.ERROR, ["Test execution error"], 0)}`, which also shows there is no `error` key.
- No Tests Found: `status is RunStatus.ERROR`, and `"No Tests Found"` appears in `verdict.problems[0]`.

Every other test must keep passing with the migrated dicts.
