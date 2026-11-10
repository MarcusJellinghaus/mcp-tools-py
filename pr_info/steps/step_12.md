# Step 12 — ruff fix report

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_12.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_ruff/reporting.py` (`format_ruff_fix_report`)
- New test: `tests/test_code_checker_ruff/test_fix_report_budget.py`; update the existing
  ruff fix tests

## WHAT
`format_ruff_fix_report(changed_files: list[str], remaining_messages: list[RuffMessage]) -> str`
(same signature).
`FIX_HINT = "Use run_ruff_check(max_issues=0) to list all remaining rules."`

## HOW
- First line: `Ruff applied fixes to {plural(n,'file')} {format_dir_split(changed_files)}:`
  (no split when n == 0). Then the first `SUMMARY_TOP` files, then
  `... and K more files` when more.
- Remaining issues: `render_summary(rows, title=f"{total} remaining issues ({k} rule types) not auto-fixable:", hint=FIX_HINT)`,
  with rows `(label, count, split)` from `group_and_sort_issues`.

## ALGORITHM
None beyond `render_summary`.

## DATA
Unchanged `str`.

## Tests (write first)
- 500 changed files + 60 remaining rules → < `TOOL_LINES` lines, contains `... and 480 more files`,
  ends with `FIX_HINT`.
- Small input: every file listed, no hint.
