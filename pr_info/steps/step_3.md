# Step 3 — Shared renderers + pylint

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_3.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- `src/mcp_tools_py/utils/report_budget.py`: add `Location`, `render_locations`,
  `render_summary`, `SUMMARY_HINT` and the constants `LOCATIONS_PER_RULE`,
  `LINES_PER_LOCATION`, `SUMMARY_TOP`
- `src/mcp_tools_py/code_checker_pylint/reporting.py`
- Tests: extend `tests/test_report_budget.py`; new
  `tests/test_code_checker_pylint/test_reporting_budget.py`; update the existing pylint
  reporting tests that assert the JSON blobs or the old hint

## WHAT
```python
class Location(NamedTuple):
    path: str
    line: int | None = None
    message: str | None = None
    details: tuple[str, ...] = ()   # extra indented lines under the row (mypy hints)

SUMMARY_HINT = "Use max_issues=0 to list all rules."
LOCATION_HINT = "narrow target_directories or fix these and rerun"

def render_locations(items: Sequence[Location], hint: str = LOCATION_HINT) -> list[str]: ...
def render_summary(
    rows: Sequence[tuple[str, int, str]],   # (label, count, dir split)
    title: str | None = None,
    top: int | None = SUMMARY_TOP,
    hint: str = SUMMARY_HINT,
) -> list[str]: ...
```

## ALGORITHM
`render_locations`:
```
rows = ordered dict keyed (path, message) -> list[Location], in first-seen order
for each of the first LOCATIONS_PER_RULE rows: nums = lines (not None) of the row
  text = f"- {path}" + (f": {', '.join(nums[:LINES_PER_LOCATION])}" if nums) + (f" (+{len(nums)-LINES_PER_LOCATION})" if more)
  text += f" — {message}" if message; emit text, then "    " + each detail of the row's first item
hidden = items in the remaining rows
if hidden: emit f"... and {hidden} more {plural('location')} in {len(rest)} more rows — {hint}"
```
`render_summary`:
```
out = [title] if title; shown = rows if top is None else rows[:top]
out += [f"- {label}: {plural(count, 'occurrence')} {split}" for shown]
rest = rows[len(shown):]
if rest: largest = 3 largest of rest by count → "S101 3444, COM812 1037"
  out += [f"... and {len(rest)} more rules ({sum} occurrences), largest: {largest}", hint]
```

## HOW (pylint)
- Replace the JSON-blob detail in both `get_prompt_for_known_pylint_code` and
  `get_prompt_for_unknown_pylint_code`. Keep the header and instruction text, then
  `Locations:` followed by `render_locations([Location(normalize_path(m.path, project_dir), m.line, m.message) ...])`,
  passing the full group (the renderer caps it).
- Delete `MAX_LOCATIONS_PER_ISSUE`, the `capped_result` slicing, the `... and N more occurrences`
  line and the `json` import.
- Remaining groups: `render_summary(rows, title=f"--- {plural(n,'additional rule')} found ({m} occurrences) ---")`.
  The old `Use max_issues={total_types} ...` hint is gone; the summary hint replaces it.
- `max_issues == 0`: `[total_line, "", *render_summary(rows, top=None)]`, then the existing
  `Use max_issues>=1 ...` line.
- `report_counts.py` stays as it is.

## DATA
Both renderers return `list[str]` lines; callers join them with `"\n"`.

## Tests (write first)
- Renderers: one row per (file, message); 25 hits in one file with the same message →
  10 numbers + `(+15)`; 15 files → 10 rows + overflow line with hint; summary with 30 rows
  → 20 rows + "largest:" naming the largest hidden ones + hint; `top=None` → all rows,
  no hint.
- pylint budget test: synthetic `PylintResult` with 1 rule × 500 messages in 60 files, plus
  40 other rules. The report from `get_pylint_prompt` (patch `get_pylint_results`) has
  < `TOOL_LINES` lines, contains no `{`/`"module"` JSON, and ends with `SUMMARY_HINT`.
- Location messages: two messages with different text in the same file give two rows.
