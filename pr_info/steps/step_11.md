# Step 11 — `--show-capture` and `-s` output on every verdict with tests

## LLM prompt
Read `pr_info/steps/summary.md` (design changes 5 and 6) and this file; issue #293 D12 and D13 define the
behaviour. Implement test-first. Run pylint, mypy and the non-integration pytest suite. One commit.

## WHERE
- `src/mcp_tools_py/checker_tools/__init__.py`
- Tests: `tests/test_checker_tools_formatting.py`

## WHAT
```python
def _format_pytest_result_with_details(
    self, test_results, show_details, show_output=False, collect_only=False,
    max_lines=TOOL_LINES, max_chars=TOOL_CHARS,
    capture: frozenset[str] = ALL_CAPTURE,
) -> str
```
Private helper `_with_passing_output(text, report, max_lines, max_chars) -> str`.

## HOW
- FAILED passes `capture` to `create_prompt_for_failed_tests`.
- With `show_output` and a report that has tests, PASSED, FAILED and ERROR append the passing output after the
  main text, bounded by what the main text left (`max_lines - lines(text)`, `max_chars - len(text)`).
- If fewer than `MIN_FENCED_LINES` lines are left, append
  `f"{DROPPED_NOTICE} passing-test output (-s)"` instead (failures take priority).

## ALGORITHM
```
_with_passing_output(text, report, max_lines, max_chars):
    lines_left = max_lines - text.count("\n") - 3; chars_left = max_chars - len(text) - 2
    if lines_left < MIN_FENCED_LINES: return text + "\n\n" + DROPPED_NOTICE + " passing-test output (-s)"
    return text + "\n\n" + create_prompt_for_passing_output(report, lines_left, chars_left)
```

## DATA
FAILED reply with `-s`: counts, failure prompt, then `Captured output of passing tests:` with stdout/stderr/log.

## Tests (write first)
FAILED + `show_output` → passing output after the failure blocks; ERROR with a report that has tests (collection
errors under `--continue-on-collection-errors`) → passing output after the error details; ERROR without tests →
unchanged; `capture=frozenset({"log"})` reaches the failure blocks; tight budget → dropped notice.
