# Step 2: Drop the false exit-code line and `collection_errors`

**Commit:** `fix(pytest): stop claiming tests failed on collection errors`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`. Implement step 2 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/verdict.py`
- `src/mcp_tools_py/code_checker_pytest/models.py`
- `src/mcp_tools_py/code_checker_pytest/utils.py`
- `src/mcp_tools_py/checker_tools/__init__.py`
- `README.md`
- `tests/test_code_checker_pytest/test_verdict.py`
- `tests/test_checker_tools_formatting.py`

## WHAT

```python
def format_collection_problems(verdict: RunVerdict) -> str: ...  # report parameter removed
```

## HOW

- `format_error_text`: skip the exit-code line when the report has failed collectors and no failed test. This replaces the `code == 2` condition.
- `_has_collection_problems(report)`: `failed_collector_count(report) > 0`.
- `_merge_problems`: remove the `collection_errors` branch.
- `format_collection_problems`: now only emits the xdist hint. The call in `checker_tools/__init__.py` loses its `report` argument.
- Remove `ErrorContext.collection_errors` (`models.py:155`) and the block in `create_error_context` (`utils.py:233-250`).
- `README.md:76`: an errored run no longer always shows the exit code. Say it shows the problems, plus the exit code unless collection failures explain it and no test failed.

## ALGORITHM

```
explained = report and _has_collection_problems(report) and failed + error == 0
if code != 0 and not explained: add the exit-code line

hint = _xdist_hint(verdict.problems)
return f"Collection problems:{hint}" if hint else ""
```

## DATA

`format_collection_problems` returns `"Collection problems:\n<hint>"`, or `""`.

## TESTS

`test_verdict.py`:

- New: exit 1 with failed collectors and no failed test has no `Exit code` line and no `some tests failed` text.
- New: exit 1 with failed collectors and a failed test keeps the exit-code line, on a verdict rendered by `format_error_text`.
- `_ctx`: remove the `collection_errors` parameter.
- Remove `test_problems_collectors_before_collection_errors` (`:106-112`).
- Remove `test_format_collection_problems_only_collection_errors` (`:211-221`).
- Update the `format_collection_problems` calls at `:226` and `:235`.

`test_checker_tools_formatting.py`:

- `_failed_report`: remove the `collection_errors` parameter.
- Rewrite `test_format_pytest_result_failed_with_collection_errors` (`:254`) to use a report with a failed collector whose longrepr contains the xdist marker. Assert the reply starts with `Collection problems:` and contains the hint before `Pytest found issues that need attention:`.
