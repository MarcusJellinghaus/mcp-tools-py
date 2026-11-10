# Step 8 — pytest passing output, verdict caps, coverage budget, `OutputBuilder` removal

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_8.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/reporting.py`: delete `OutputBuilder`,
  `MAX_OUTPUT_LINES` and `MAX_COLLECTOR_IDS`; rewrite `create_prompt_for_passing_output`
- `src/mcp_tools_py/code_checker_pytest/verdict.py`: `cap_problems`,
  `format_collect_only_text`, `_ERROR_TAIL_LINES`
- `src/mcp_tools_py/utils/report_budget.py`: add `MAX_COLLECTOR_IDS`, `ERROR_TAIL_LINES`
- `src/mcp_tools_py/checker_tools/__init__.py`: `_format_pytest_result_with_details` gains `max_lines`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`: build the coverage digest before formatting
- `docs/architecture/architecture.md`: drop the `OutputBuilder` "Builder Pattern" bullet
  and the `OutputBuilder` mention in the `code_checker_pytest` entry
- New test: `tests/test_code_checker_pytest/test_output_budget.py`; update the tests that
  import `OutputBuilder` / `MAX_OUTPUT_LINES` or assert the old truncation marker

## WHAT
```python
def create_prompt_for_passing_output(report: PytestReport, max_lines: int = TOOL_LINES) -> str
def cap_problems(problems: list[str]) -> str              # bound_text("\n".join(problems), hint=PROBLEMS_HINT)
def format_collect_only_text(report: PytestReport) -> str # bound_text(..., hint=COLLECT_HINT)
CheckerTools._format_pytest_result_with_details(test_results, show_details, show_output=False,
                                                collect_only=False, max_lines=TOOL_LINES) -> str
```
Hints:
- `SHOW_OUTPUT_HINT = "Use extra_args=['<nodeid>', '-s'] to see one test's output."`
- `COLLECT_HINT = "Narrow the selection (a path or -k in extra_args) to list fewer tests."`
- `PROBLEMS_HINT = "Narrow the selection (a path or -k in extra_args) and rerun to see the rest."`

## HOW
- Passing output: build the same text as today, then return
  `bound_text(text, max_lines, hint=SHOW_OUTPUT_HINT)`. `bound_text` closes any fence
  left open at the cut.
- `verdict.py` imports `bound_text`, `TOOL_LINES` and `ERROR_TAIL_LINES` from
  `report_budget`, and no longer imports `OutputBuilder` or `MAX_OUTPUT_LINES`.
- `_render_collector_group` uses `MAX_COLLECTOR_IDS` from `report_budget`.
- `checker_tools/__init__.py` imports `MAX_FAILURES` and `TOOL_LINES` from `report_budget`,
  and passes `max_lines` into `create_prompt_for_failed_tests` and
  `create_prompt_for_passing_output`.
- `pytest_tool.py`: move the coverage block (`finish_coverage_run` → digest) above the
  `_format_pytest_result_with_details` call. Then call it with
  `max_lines=max(TOOL_LINES // 2, TOOL_LINES - digest.count("\n") - 1)`, and append the
  digest after the result as today. The digest stays local (bounded by `max_modules`).
  Without coverage, `max_lines=TOOL_LINES`.
- `toolkit.py` keeps importing `cap_problems`; no change there.

## ALGORITHM
```
digest = coverage digest (or None) computed first
budget = TOOL_LINES if digest is None else max(TOOL_LINES // 2, TOOL_LINES - lines(digest))
result = _format_pytest_result_with_details(..., max_lines=budget)
result = notes + result + ("\n\n" + digest if digest)
```

## DATA
Unchanged return types.

## Tests (write first)
- `show_output` with 50 passing tests × 50 lines of stdout → ≤ `TOOL_LINES` lines, even
  fence count, ends with `SHOW_OUTPUT_HINT`.
- `--collect-only` with 2000 IDs → ≤ `TOOL_LINES` lines, keeps the header line, ends with `COLLECT_HINT`.
- `cap_problems` with 1000 lines of problems → ≤ `TOOL_LINES` lines, ends with `PROBLEMS_HINT`.
- `coverage=True` with 15 failures and a digest → the whole response is < `GUARD_LINES`
  lines (the guard does not fire), contains the failed-ID list and the full digest
  (patch the runner and coverage helpers as in `tests/test_pytest_tool_coverage.py`).
