# Step 5 — Warning groups and duration entries

## LLM prompt
Read `pr_info/steps/summary.md` (design change 3) and this file; issue #293 D9, the `--durations` row and the
"Multi-line warning messages" constraint define the behaviour. Implement test-first. Run pylint, mypy and the
non-integration pytest suite. One commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/report_data.py`
- Tests: `tests/test_code_checker_pytest/test_report_data.py`

## WHAT
```python
@dataclass(frozen=True)
class WarningGroup:
    category: str
    message: str      # full text (grouping key part)
    count: int
    first: str        # "path:lineno", path via relative_path

def warning_groups(report: PytestReport) -> list[WarningGroup]:
    """Grouped by (category, message); sorted by count desc, ties in first-seen order."""

def warning_line(group: WarningGroup) -> str:
    """'DeprecationWarning: <first message line> — 30× (first: tests/x.py:12)'."""

@dataclass(frozen=True)
class Duration:
    seconds: float
    when: str         # setup / call / teardown
    nodeid: str

def durations(report: PytestReport) -> list[Duration]:
    """Every stage of every test, slowest first."""

def stage_seconds(report: PytestReport) -> float:
    """Sum of all test stage durations (D10: not report.duration)."""
```

## ALGORITHM
```
warning_groups: groups = {}
    for w in report.warnings or []: key = (w.category or "Warning", w.message)
        first = f"{relative_path(w.filename, report.root)}:{w.lineno}" on first sight; count += 1
    return sorted(groups, key=-count)   # sorted() is stable
durations: [Duration(stage.duration, name, test.nodeid) for test, name, stage if stage] sorted desc by seconds
```

## DATA
- 30 warnings, same category + message, different locations → one group, `count == 30`, `first` = first location.
- Same message, `UserWarning` and `DeprecationWarning` → two groups.
- Multi-line message: `warning_line` shows only the first line.

## Tests (write first)
Cases above; a warning without `filename` (first = `"?"`); `durations` mixes stages and sorts; `stage_seconds`
sums setup + call + teardown.
