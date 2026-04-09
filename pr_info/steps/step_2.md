# Step 2: Reporting (with tests)

> **Context**: See `pr_info/steps/summary.md` for the full plan. This is step 2 of 5.

## Goal

Create the reporting layer that groups ruff violations by rule code, sorts them by prefix category then frequency, and formats LLM-optimized output with `max_issues` detail/summary control.

## LLM Prompt

```
Read pr_info/steps/summary.md for full context, then implement step 2.

Create reporting.py in code_checker_ruff with grouping/sorting/formatting logic.
Follow TDD: write tests first in tests/test_code_checker_ruff/test_reporting.py.
Mirror pylint's _group_and_sort_issues pattern but simpler — no instruction lookup,
just group→sort→format with ruff's URL field for docs links.

Sort order: rule prefix category (E > W > D > DOC > etc.) then frequency descending.

After implementation, run all three code quality checks (pylint, pytest, mypy).
Fix any issues before committing.
```

## WHERE

**Create:**
- `src/mcp_tools_py/code_checker_ruff/reporting.py`
- `tests/test_code_checker_ruff/test_reporting.py`

**Modify:**
- `src/mcp_tools_py/code_checker_ruff/__init__.py` — add re-exports

## WHAT

### `reporting.py`

```python
MAX_LOCATIONS_PER_ISSUE: int = 50

# Lower number = higher priority
RULE_PREFIX_PRIORITY: dict[str, int] = {
    "E": 0,   # errors
    "W": 1,   # warnings
    "F": 2,   # pyflakes
    "D": 3,   # pydocstyle
    "DOC": 4, # pydoclint
    # ... everything else gets 99
}

class RuffIssueGroup(NamedTuple):
    code: str                     # e.g. "D100"
    messages: list[RuffMessage]

def get_rule_prefix(code: str) -> str:
    """Extract prefix from rule code: 'D100' → 'D', 'DOC201' → 'DOC'."""

def group_and_sort_issues(messages: list[RuffMessage]) -> list[RuffIssueGroup]:
    """Group by code, sort by prefix priority then frequency (descending)."""

def format_ruff_check_report(
    messages: list[RuffMessage],
    max_issues: int = 1,
) -> str | None:
    """Format ruff check results into LLM prompt. Returns None if no issues."""

def format_ruff_fix_report(
    changed_files: list[str],
    remaining_messages: list[RuffMessage],
) -> str:
    """Format ruff fix results: changed files + remaining error summary."""
```

## HOW

- `get_rule_prefix`: strip trailing digits from code string (e.g. `"DOC201"` → `"DOC"`, `"E501"` → `"E"`)
- Sorting: `(RULE_PREFIX_PRIORITY.get(prefix, 99), -len(group.messages))`
- `format_ruff_check_report`: top N groups get detail (file:line per occurrence, capped at `MAX_LOCATIONS_PER_ISSUE`), remaining get one-line summary counts. Include URL from first message in each group.
- `format_ruff_fix_report`: list changed files, then brief summary of remaining unfixed violations if any

## ALGORITHM — `format_ruff_check_report`

```
1. groups = group_and_sort_issues(messages)
2. if not groups: return None
3. for group in groups[:max_issues]:
4.   format detailed section: code, message, url, locations (capped)
5. for group in groups[max_issues:]:
6.   append one-line summary: "- CODE: N occurrences"
7. return joined sections
```

## ALGORITHM — `format_ruff_fix_report`

```
1. lines = ["Ruff applied fixes to N files:"]
2. for file in changed_files: append "- file"
3. if remaining_messages:
4.   groups = group_and_sort_issues(remaining_messages)
5.   append "N remaining issues (M rule types) not auto-fixable:"
6.   for group: append "- CODE: count occurrences"
7. return joined lines
```

## DATA

**Input**: `list[RuffMessage]` from step 1's parser
**Output**: formatted string or None

Detail section format (per issue group):
```
ruff found N issues with rule CODE (rule-url).
{message from first occurrence}
Locations:
- filename:line:column
- filename:line:column
... and M more occurrences
```

## Tests — `test_reporting.py`

Helper: `_make_ruff_message(code="D100", filename="src/foo.py", line=1, ...)` with sensible defaults.

Test cases:
1. `test_get_rule_prefix` — "E501"→"E", "DOC201"→"DOC", "D100"→"D"
2. `test_group_and_sort_empty` — [] → []
3. `test_group_and_sort_single_code` — all same code → one group
4. `test_group_and_sort_by_prefix_priority` — E before W before D
5. `test_group_and_sort_by_frequency_within_prefix` — same prefix, more frequent first
6. `test_format_check_report_no_issues` — empty messages → None
7. `test_format_check_report_max_issues_1` — 3 rule types, only first detailed
8. `test_format_check_report_locations_capped` — >50 locations → "and N more"
9. `test_format_fix_report_with_remaining` — changed files listed + remaining summary
10. `test_format_fix_report_no_remaining` — changed files only, no remaining section

## Commit

```
feat(ruff): add reporting layer with grouping, sorting, and LLM formatting

- Group violations by rule code, sort by prefix category (E>W>D>DOC) then frequency
- format_ruff_check_report() with max_issues detail/summary control
- format_ruff_fix_report() for fix results (changed files + remaining errors)
- Unit tests for grouping, sorting, and both report formats
```
