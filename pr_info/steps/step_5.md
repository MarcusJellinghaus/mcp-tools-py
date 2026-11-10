# Step 5 — bandit + deptry

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_5.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_bandit/reporting.py`
- `src/mcp_tools_py/code_checker_deptry/reporting.py`
- New tests: `tests/test_code_checker_bandit/test_reporting_budget.py`,
  `tests/test_code_checker_deptry/test_reporting_budget.py`; update the existing tests

## WHAT
Signatures unchanged: `format_bandit_report(messages, errors, max_issues=1)` and
`format_deptry_report(messages, max_issues=1)`.

## HOW
- bandit detail: keep the header, CWE and `issue_text` lines. Then `Locations:` +
  `render_locations([Location(m.filename, m.line_number) ...])` (no per-location message,
  because `issue_text` is per test id). Remaining groups:
  `render_summary(rows, title="--- N additional rules found (M occurrences) ---")`, with
  label `f"{test_id} {test_name} ({severity})"`. `max_issues == 0` → `render_summary(rows, top=None)`.
- bandit "File errors" list: unchanged. It is short in practice, and the guard covers it.
- deptry detail: `render_locations([Location(m.file, m.line, f"{m.module} {m.message}" if m.line is not None else f"'{m.module}'") ...])`.
  Remaining groups → `render_summary`.
- Both tools accept `target_directories`, so keep the default `LOCATION_HINT`.
- Delete both `MAX_LOCATIONS_PER_ISSUE` constants and the overflow lines.

## ALGORITHM
None beyond the renderers.

## DATA
Unchanged.

## Tests (write first)
For each tool, a parametrised budget test: 1 rule × 400 locations in 50 files plus 40 other
rules → < `TOOL_LINES` lines, ends with `SUMMARY_HINT`, and the location overflow line
contains `LOCATION_HINT`.
