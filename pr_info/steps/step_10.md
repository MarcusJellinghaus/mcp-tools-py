# Step 10 — `⚠️ Warnings: N` count

## LLM prompt
Read `pr_info/steps/summary.md` (design change 8) and this file; issue #293 D16 and D19 define where the count
appears. Implement test-first. Run pylint, mypy and the non-integration pytest suite. One commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/reporting.py`
- `src/mcp_tools_py/code_checker_pytest/verdict.py`
- `src/mcp_tools_py/checker_tools/__init__.py`
- Tests: `tests/test_code_checker_pytest/test_verdict.py`, `tests/test_checker_tools_formatting.py`,
  `tests/test_toolkit_test.py`

## WHAT
```python
# reporting.py
def warnings_part(report: PytestReport | None) -> str:
    """' | ⚠️ Warnings: N' when the report has warnings, else ''."""

# verdict.py
def format_error_text(report, verdict, show_warnings: bool = False) -> str
```

## HOW
- `format_error_text`: when the summary line is rendered and `show_warnings`, append `warnings_part(report)` to it.
  The "Pytest run did not complete." line gets nothing.
- `CheckerTools._format_pytest_result_with_details` (called only by `run_pytest_check`): PASSED and FAILED append
  `warnings_part(report)` to `summary_text`; ERROR calls `format_error_text(report, verdict, show_warnings=True)`.
  SUSPICIOUS text unchanged.
- `get_test_summary` and the toolkit stay without the count.

## DATA
`Pytest check completed. Collected 3 tests in 0.20 seconds | ✅ Passed: 3 | ⚠️ Warnings: 2`.

## Tests (write first)
PASSED/FAILED/ERROR-with-report get the count; SUSPICIOUS and "did not complete" do not; `format_error_text`
default has no count; a toolkit test through `_run_test` with a warning-bearing report has no `⚠️ Warnings`.
