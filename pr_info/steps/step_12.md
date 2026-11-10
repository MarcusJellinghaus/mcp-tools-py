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
  `f"... and {K} more files — {FILES_HINT}"` when more, with
  `FILES_HINT = "narrow target_directories to list fewer changed files"`. The file
  overflow line carries its own hint, independent of `FIX_HINT`.
- Remaining issues: `render_summary(rows, title=f"{total} remaining issues ({k} rule types) not auto-fixable:", hint=FIX_HINT, detail_hint="Use run_ruff_check to see their locations.")`,
  with rows `(label, count, split)` from `group_and_sort_issues` (ruff fix has no
  `max_issues`, so the default `DETAIL_HINT` does not apply).

## ALGORITHM
None beyond `render_summary`.

## DATA
Unchanged `str`.

## Tests (write first)
- 500 changed files + 60 remaining rules → < `TOOL_LINES` lines, contains `... and 480 more files`,
  ends with `FIX_HINT`.
- 500 changed files + 5 remaining rules → the `... and 480 more files` line contains
  `FILES_HINT`; no `FIX_HINT`-dependent overflow.
- Small input: every file listed, no hint.
