# Step 7 — pytest failure rendering

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_7.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/reporting.py`: rewrite the failed-test part
  (`create_prompt_for_failed_tests`, `_format_test_info`, `_format_test_output`,
  `_format_test_setup_info`, `_process_failed_tests`, `_process_failed_collectors`,
  `_get_failed_tests`)
- `src/mcp_tools_py/utils/report_budget.py`: add `MAX_FAILURES`, `FAILED_IDS`
- `src/mcp_tools_py/checker_tools/__init__.py`: update the call
- `src/mcp_tools_py/code_checker_pytest/runners.py:562`: delete the
  `create_prompt_for_failed_tests(test_results)` call and the `failed_tests_prompt` key of
  the returned dict (and its docstring line). No source code reads that key; it relied on
  the old default of 1 reported test. Update `tests/test_code_checker/test_runners.py`
  (lines 189 and 319–320), which only assert on that key.
- New test: `tests/test_code_checker_pytest/test_failure_budget.py`; update the existing
  failure-prompt tests in `tests/test_code_checker_pytest/test_reporting.py` (keep that
  file under 750 lines; move tests out if needed)

## WHAT
```python
PYTEST_HINT = "Use extra_args=['<nodeid>', '-vv'] to see one test in full."

def create_prompt_for_failed_tests(
    test_session_result: PytestReport,
    include_print_output: bool = True,
    max_failures: int = MAX_FAILURES,
    max_lines: int = TOOL_LINES,
    max_chars: int = TOOL_CHARS,
) -> Optional[str]: ...

def _render_test(test: Test, include_print_output: bool, max_lines: int, max_chars: int) -> str: ...
def _fenced(label: str, text: str, max_lines: int, max_chars: int) -> str: ...
```
`max_number_of_tests_reported` is removed (it duplicated `max_failures`). Update
`CheckerTools._format_pytest_result_with_details`. Keep `MAX_FAILURES` exported from
`reporting.py` by import from `report_budget` until step 8 cleans up the imports.

## HOW
- `_fenced(label, text, n, c)` returns
  `f"  {label}:\n```\n{bound_text(text, n - 3, c, keep='tail')}\n```"`. The fences are
  written outside the bounded body, so they are always closed. When `n - 3` is below
  `bound_text`'s overhead, it relies on step 1's lower bound (marker and hint only, no
  slicing), so a small leftover budget never raises.
- `_render_test` writes sections in this order, each taking the budget left over:
  1. `Test ID: <nodeid> - outcome <outcome>`, then `  Error Message: <crash.message>`
  2. longrepr if present (`_fenced("Longrepr", ...)`), else the traceback entries
  3. stderr, then stdout (`_fenced`, only with `include_print_output`)
  4. setup info when setup failed: outcome, crash, setup longrepr (or setup traceback
     when it has no longrepr), setup stderr/stdout.
  A section that does not fit in what is left is skipped.
- Collector section first, unchanged in content, bounded with
  `bound_text(text, max_lines // 3, max_chars // 3)`.
- The `====` separator lines and the closing question stay.

## ALGORITHM
```
failed = all failed/error tests; candidates = failed[:max_failures]
reserve = min(len(failed), FAILED_IDS) + 3 if len(failed) > 1 else 0
left = max_lines - lines(collector part) - reserve - 3      # closing question + hint
chars_left = max_chars - chars(collector part) - chars(reserved ID list) - chars(closing question + hint)
for i, test in enumerate(candidates): per = left // (len(candidates) - i); if per < 6: break
    block = _render_test(test, per, chars_left // (len(candidates) - i)); append
    left -= lines(block); chars_left -= chars(block)
undetailed = failed tests without a block → if any: "Failed tests without details (N):" + first FAILED_IDS ids + "... and K more"
append closing question, then PYTEST_HINT
```

## DATA
Returns `Optional[str]` (None when nothing failed), as before.

## Tests (write first)
- 15 failing tests; test 1 has 400 lines of stdout and a longrepr → output ≤ `TOOL_LINES`
  lines, test 1's longrepr appears before its stdout, all 15 node IDs appear somewhere,
  the fence count is even, and the output ends with `PYTEST_HINT`.
- A test with a longrepr has no `Traceback:` section; a test without one shows the traceback.
- 1 failure → no "Failed tests without details" list.
- A longrepr of 1000 lines keeps its last line (`E   assert ...`).
