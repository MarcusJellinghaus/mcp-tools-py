# Step 12 — Wire notes and tail block into `run_pytest_check`

## LLM prompt
Read `pr_info/steps/summary.md` (design changes 5 and 7) and this file; issue #293 D17, D19 and the "Budget"
constraint define placement and predicate. Implement test-first. Run pylint, mypy and the non-integration pytest
suite. One commit.

## WHERE
- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `src/mcp_tools_py/code_checker_pytest/report_extras.py`
- Tests: `tests/test_code_checker_pytest/test_config_notes_reply.py` (or a new reply-level test module beside it,
  mocking `check_code_with_pytest` the same way)

## WHAT
```python
# report_extras.py
def report_tail(report: PytestReport, flags: ReportFlags, max_lines: int, max_chars: int) -> str:
    """Sections (step 7) then the hint line (step 8, kept last); '' when both are empty."""

def has_tests(report: PytestReport | None, collect_only: bool) -> bool:
    """D19 predicate: a report with at least one test entry, not --collect-only."""
```

## HOW (in `run_pytest_check`, after `effective` is built)
```
flags = report_flags(effective)
result = _format_pytest_result_with_details(..., capture=capture_kinds(flags.show_capture))
report = test_results.get("test_results")
if has_tests(report, sanitized.collect_only):
    notes += flag_notes(flags)                                   # with the existing top notes
    tail = report_tail(report, flags, max_lines - lines(result), max_chars - len(result))
    if tail: result = f"{result}\n\n{tail}"
# then the existing top-notes prefix and the coverage digest suffix
```
`report_tail` reserves one line for the hint before giving the rest to `report_sections`.

## DATA
- Clean run, no flags, fast: one line. With `addopts = -ra`: still one line.
- Skips + warnings: summary, blank line, hint line.
- `addopts = --durations=10`: durations section on every run.
- `--snapshot-update` with a report that has tests: note at the top; ERROR without tests: no note.

## Tests (write first)
Through the registered `run_pytest_check` with `check_code_with_pytest` mocked: the cases above; FAILED run keeps
failures before the tail; `--collect-only` gets no tail; `-rx` note appears only when passed in the call.
