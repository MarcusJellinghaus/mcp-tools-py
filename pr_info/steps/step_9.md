# Step 9 — Exit 5: report plumbing and skip block

## LLM prompt
Read `pr_info/steps/summary.md` (design change 9) and this file; issue #293 D18 and the "Exit-5 plumbing"
constraint define the behaviour. Implement test-first. Run pylint, mypy and the non-integration pytest suite.
One commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/runners.py`
- `src/mcp_tools_py/code_checker_pytest/report_extras.py`
- `src/mcp_tools_py/checker_tools/__init__.py` (ERROR branch of `_format_pytest_result_with_details`)
- Tests: `tests/test_code_checker_pytest/test_runners.py`, `tests/test_checker_tools_formatting.py`,
  `tests/test_code_checker_pytest/test_report_extras.py`

## WHAT
```python
# runners.py
_SKIP_REPORT_ATTR = "pytest_skip_report"
def _read_report(path: str) -> PytestReport | None:
    """Parse the JSON report; None when missing or unreadable."""

# report_extras.py
def skipped_block(report: PytestReport) -> str:
    """'⏭️ Skipped: N' then the folded skip lines; '' when nothing was skipped."""
```
`check_code_with_pytest` error return gains `"skip_report": getattr(e, _SKIP_REPORT_ATTR, None)`; the success
return gains `"skip_report": None` (key present on every return, like `exit_code`).

## ALGORITHM
```
run_tests, returncode == 5:
    error = ValueError(f"No Tests Found: ...{detail}")          # text unchanged
    setattr(error, _SKIP_REPORT_ATTR, _read_report(temp_report_file)); raise error   # before finally deletes temp dir
_read_report: if not isfile → None; try parse_pytest_report(read_file(path)) except (OSError, ValueError, KeyError, TypeError) → None
delete the unreachable `elif process.returncode == 5 and report_exists` branch
CheckerTools ERROR branch: text = format_error_text(...); block = skipped_block(skip_report) if skip_report; append "\n" + block if block
```

## DATA
Reply on exit 5 with two module-skipped files: the unchanged error text (`Pytest run reported an error.` …
`Problems:` … `No Tests Found…`), then `⏭️ Skipped: 2` and `SKIPPED [1] tests/test_a.py:3: no db` lines. Status
stays ERROR; `verdict.problems` unchanged, so the toolkit's "No Tests Found" match still works.

## Tests (write first)
- `run_tests` with mocked `execute_command` returning 5 and a written report file → the raised `ValueError` has
  the report attached; without a file / with invalid JSON → attribute is `None`, message unchanged.
- `check_code_with_pytest` returns `skip_report`.
- Formatter: ERROR verdict + `skip_report` with a skipped collector → block appended after Problems; without it the
  text is unchanged.
