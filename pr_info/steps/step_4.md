# Step 4 — ruff check

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_4.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_ruff/reporting.py` (`format_ruff_check_report` only)
- New test: `tests/test_code_checker_ruff/test_reporting_budget.py`; update the existing
  ruff reporting tests

## WHAT
`format_ruff_check_report(messages, max_issues=1) -> Optional[str]`: same signature.

## HOW
- Detail section: keep the header line `ruff found N issues with rule <label> <split>.`.
  Drop the first-occurrence `message_text` line. Then `Locations:` +
  `render_locations([Location(m.filename, m.line, m.message) for m in group.messages])`.
  Each location keeps its own message (fixes E712-style messages), and identical
  messages collapse per file.
- Delete `MAX_LOCATIONS_PER_ISSUE` and the overflow line.
- Remaining groups: `render_summary(rows, title=f"--- {plural(n,'additional rule')} found ({m} occurrences) ---")`,
  rows `(label, count, split)`. Keep the prefix-priority sort order; `render_summary`
  names the largest hidden rules.
- `max_issues == 0`: `render_summary(rows, top=None)` with no title, as before (counts only).
- `format_ruff_fix_report` is not touched here (step 12).

## ALGORITHM
None beyond the renderers.

## DATA
Unchanged return type.

## Tests (write first)
- Budget test: 8000 messages across 150 rules (S101 with 3444 and COM812 with 1037 sorted
  below many 1-hit E/W/F rules), `max_issues=2` → < `TOOL_LINES` lines, contains
  `--- 148 additional rules`, `largest: S101 3444, COM812 1037`, and ends with `SUMMARY_HINT`.
- Per-location message: two E712 messages with different text show both texts.
