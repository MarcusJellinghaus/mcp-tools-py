# Step 1: Group failed collectors by cause on both paths

**Commit:** `fix(pytest): group failed collectors by cause`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`. Implement step 1 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/reporting.py`
- `src/mcp_tools_py/code_checker_pytest/verdict.py`
- `src/mcp_tools_py/toolkit.py`
- `tests/test_code_checker_pytest/test_collector_groups.py` (new)
- `tests/test_code_checker_pytest/test_verdict.py`
- `tests/test_code_checker/test_reporting.py`
- `tests/test_toolkit_test.py`

## WHAT

In `reporting.py`:

```python
XDIST_MARKER = "Different tests were collected"   # moved from verdict.py
MAX_COLLECTOR_IDS = 10

def failed_collector_count(report: PytestReport) -> int: ...      # distinct node IDs
def group_failed_collectors(report: PytestReport) -> list[str]: ...  # one text per distinct error
def collectors_failed_line(report: PytestReport) -> str: ...      # "" when none failed
def _collector_key(longrepr: str) -> str: ...
```

## HOW

- `verdict.py` imports `XDIST_MARKER` and the helpers from `reporting`, so `from ...verdict import XDIST_MARKER` in tests keeps working.
- `_merge_problems`: `items = group_failed_collectors(report)`, then the existing `collection_errors` branch (removed in step 2) and tail fallback. Remove `_dedup_key` and the `seen` loop.
- `format_error_text`: when `collectors_failed_line(report)` is not empty, add it and a blank line right after `Problems:`.
- `toolkit.py`, the FAILED-with-no-findings return (`:176`), which renders `cap_problems(verdict.problems)` directly: when `collectors_failed_line(report)` is not empty, add it and a blank line before the capped problems. With no failed collector the summary stays as it is.
- `_process_failed_collectors(report, output)` takes the report and returns `True` when no collector failed. Otherwise it adds the line, a blank line, then each group followed by a blank line. Stop on truncation, as now.
- `create_prompt_for_failed_tests`: pass the report to it and keep the early return on truncation.
- Remove `_format_collector_info`.

## ALGORITHM

```
_collector_key(text): XDIST_MARKER if marker in text
    else "\n".join(lines starting with "E   ") if any
    else last non-empty line, or ""
group: for each failed collector with a longrepr, key -> (first longrepr, ordered unique node IDs)
render: if the first longrepr has E lines, the joined E lines, then the longrepr; otherwise the longrepr alone
    if len(ids) > 1: "same error in {n} more collector(s): a, b, … and {m} more"
    list ids[1:] capped at MAX_COLLECTOR_IDS; omit "… and m more" when m == 0
```

## DATA

- `collectors_failed_line`: `47 collectors failed (2 distinct errors)`, singular `1 collector failed (1 distinct error)`.
- `failed_collector_count` counts every failed collector's distinct `nodeid`, including those with no `longrepr`.

## TESTS

`test_collector_groups.py` (use small `Collector`/`PytestReport` builders):

- Identical `E   ` lines in different collectors give one group, with `same error in 1 more collector: ...`.
- Two conftest longreprs starting with the same `importlib` frame but with different `E   ` lines give two groups (the `_dedup_key` bug).
- Two syntax errors whose `E   ` lines name different files give two groups.
- A collector repeated with the same node ID (xdist) counts once and shows no `same error` line.
- 13 collectors in one group: 10 IDs listed, then `… and 2 more`.
- No `E   ` line: the group key falls back to the last non-empty line, and the text has no duplicated headline.
- Xdist marker texts with different workers give one group.
- A collector without `longrepr` is counted but forms no group.
- ERROR path: `format_error_text` contains the count line, on a report with collectors.
- FAILED path: `create_prompt_for_failed_tests` contains the count line.

`test_toolkit_test.py`, using `_run_with`: a FAILED verdict with a failed collector and no failing test returns `status == "error"`, and the summary contains `1 collector failed (1 distinct error)` before the problem text.

`test_verdict.py`: rewrite `test_dedup_same_first_line` (`:163`) so the two collectors, whose last lines differ, stay separate.

`test_code_checker/test_reporting.py`: at `:572` and `:833`, assert `1 collector failed (1 distinct error)` instead of the old header. Remove the `test_broken.py` assertion at `:573`, because a single-collector group has no node ID line and that fixture's longrepr doesn't name the file. `:834` still passes through the failing test's ID.
