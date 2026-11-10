# Step 6 — mypy

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_6.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_mypy/reporting.py`
- `src/mcp_tools_py/checker_tools/mypy_tool.py` (default + docstring)
- `src/mcp_tools_py/utils/report_budget.py`: add `HINT_LINES = 5`
- New test: `tests/test_code_checker_mypy/test_reporting_budget.py`; update the existing
  mypy reporting/tool tests (default, location count, notes)

## WHAT
```python
def format_hint_lines(hint: str | None) -> list[str]   # now capped at HINT_LINES
def create_mypy_prompt(result: MypyResult, max_issues: int = 3) -> str | None
def get_mypy_prompt(..., max_issues: int = 3) -> str | None
run_mypy_check(..., max_issues: int = 3)                 # MCP tool
```
`None` is no longer accepted. `0` means counts only.

## HOW
- `format_hint_lines`: indent as before, keep the first `HINT_LINES` lines, then
  `    ... and N more hint lines`. The toolkit's mypy `fix_text` uses it too, so one cap
  covers both.
- Detailed groups: `render_locations([Location(m.file, m.line if m.line >= 0 else None, m.message, tuple(format_hint_lines(m.hint))) ...])`.
  Keep the rc-2 rule: the group holding the last error is always detailed. If the last
  error falls outside the first `LOCATIONS_PER_RULE` rows, put its `Location` first.
- Delete `MAX_LOCATIONS_PER_CODE`.
- Standalone notes (`severity == "note"`, `code` = the parent's code or `misc`), when
  `max_issues > 0`:
  - note code is in a detailed group → add its `Location` to that group's items, with
    the message prefixed `note: `;
  - otherwise → a `Notes (N)` section: `render_locations` over those notes.
- Summarised groups: `render_summary(rows, title=...)`. Rows `(code, count, split)`.
  `max_issues == 0` → `render_summary(rows, top=None)`.
- Keep the run-signal lines first and the "To fix these issues" trailer.
- `mypy_tool.py` docstring: "Number of error codes shown in detail (10 location rows each).
  Default 3. 0 = counts only ...". Drop the "None (default) details every code" sentence.

## ALGORITHM
```
groups sorted by (-count, code); detailed = first max_issues groups (+ last-error group on rc 2)
notes_by_code: notes whose code is in detailed codes; loose_notes: the rest
for each detailed group: header; render_locations(group items + its notes)
if loose_notes and max_issues > 0: "Notes (N)" + render_locations(loose_notes)
summarised groups → render_summary
```

## DATA
Unchanged return types.

## Tests (write first)
- Budget test: 30 codes × 100 errors, each error with an 8-line hint, plus 200 notes →
  default call has < `TOOL_LINES` lines, details exactly 3 codes, contains `SUMMARY_HINT`
  and `LOCATION_HINT`, and still ends with the "To fix these issues" trailer; hints show
  ≤ `HINT_LINES` lines + `... and N more hint lines`.
- A note whose code matches a detailed group appears inside that group; any other note
  appears under `Notes (`.
- `max_issues=0` → no locations, all codes listed.
