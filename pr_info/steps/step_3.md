# Step 3: LLM-Optimized Reporting + Tests

> **Context**: Read `pr_info/steps/summary.md` first for full architecture overview.

## Prompt

```
Implement Step 3 of Issue #149 (bandit security linter).
Read pr_info/steps/summary.md for architecture context, then read this step file.

Create the reporting module that groups bandit findings by test_id, sorts by
severity/confidence/frequency, and formats an LLM-optimized report.

Follow the pattern from code_checker_ruff/reporting.py but use severity-based
sorting instead of prefix-based sorting.

Reference tests/test_code_checker_ruff/test_reporting.py for test structure.

After implementation, run all three code quality checks (pylint, pytest, mypy)
using MCP tools with the recommended fast unit test exclusions.
Commit: "feat(bandit): add LLM-optimized reporting with tests"
```

## WHERE

- **Create**: `src/mcp_tools_py/code_checker_bandit/reporting.py`
- **Create**: `tests/test_code_checker_bandit/test_reporting.py`
- **Modify**: `src/mcp_tools_py/code_checker_bandit/__init__.py` — add re-exports

## WHAT

### `reporting.py`

```python
MAX_LOCATIONS_PER_ISSUE: int = 50

SEVERITY_PRIORITY: dict[str, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
CONFIDENCE_PRIORITY: dict[str, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

class BanditIssueGroup(NamedTuple):
    test_id: str
    messages: list[BanditMessage]

def group_and_sort_issues(messages: list[BanditMessage]) -> list[BanditIssueGroup]:
    """Group by test_id, sort by (severity, confidence, -frequency)."""

def format_bandit_report(
    messages: list[BanditMessage],
    errors: list[str],
    max_issues: int = 1,
) -> str | None:
    """Format bandit results into LLM-optimized report. Returns None if no issues and no errors."""
```

### ALGORITHM — `group_and_sort_issues`

```
1. Group messages by test_id into dict[str, list[BanditMessage]]
2. Build BanditIssueGroup for each group
3. Sort by (SEVERITY_PRIORITY[severity], CONFIDENCE_PRIORITY[confidence], -len(messages))
   - Use severity/confidence from first message in each group (all same test_id = same severity)
4. Return sorted list
```

### ALGORITHM — `format_bandit_report`

```
1. Build sections list
2. If errors exist: add "File errors:" section at top with each error on its own line
3. Group and sort messages via group_and_sort_issues()
4. If no groups and no errors: return None
5. For top max_issues groups: add detailed section with test_id, severity, confidence, 
   issue_text, CWE reference (id + link), and file:line locations (capped at MAX_LOCATIONS_PER_ISSUE)
6. For remaining groups: add summary line "- B1xx (SEVERITY): N occurrences"
7. Return "\n\n".join(sections)
```

### DATA

**Detailed section format** (per group):
```
bandit found N issues with B101 (assert_used) [severity: LOW, confidence: HIGH]
CWE-703: https://cwe.mitre.org/data/definitions/703.html
Use of assert detected.
Locations:
- src/foo.py:10
- src/bar.py:25
```

**Summary line format**:
```
- B101 (LOW): 5 occurrences
```

**Errors section format** (at top of report):
```
File errors (files not scanned):
- bad.py: syntax error
- other.py: encoding error
```

### Tests (`test_reporting.py`)

| Test | What it validates |
|------|-------------------|
| `test_group_and_sort_empty` | Empty list → empty list |
| `test_group_and_sort_by_severity` | HIGH before MEDIUM before LOW |
| `test_group_and_sort_by_confidence_tiebreak` | Same severity → HIGH confidence first |
| `test_group_and_sort_by_frequency_tiebreak` | Same severity+confidence → more frequent first |
| `test_format_no_issues_returns_none` | No messages, no errors → None |
| `test_format_errors_only` | Only file errors → errors section, not None |
| `test_format_max_issues_detail_and_summary` | 3 groups, max_issues=1 → 1 detailed + 2 summary |
| `test_format_includes_cwe_reference` | CWE ID + link in detailed section |
| `test_format_locations_capped` | >50 locations → capped with "... and N more" |
| `test_format_errors_at_top` | Errors section appears before findings |

Use a `_make_bandit_message()` helper for building test BanditMessage objects.

## HOW

- Import `BanditMessage` from `.models`
- Use `collections.defaultdict` for grouping (same as ruff)
- No external dependencies beyond stdlib
