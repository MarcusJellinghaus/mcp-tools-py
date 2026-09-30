# Step 7 — Mypy report: total line, count order, split, max_issues, hints, notes

## LLM prompt

Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_7.md`) only.
Tests first. Run pylint, pytest (`-n auto`), mypy, lint-imports; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_mypy/reporting.py` — `create_mypy_prompt`, `get_mypy_prompt`
- `src/mcp_tools_py/checker_tools/__init__.py` — `_format_mypy_result`
- `tests/test_code_checker_mypy/test_reporting.py`, `tests/test_checker_tools_formatting.py`

## WHAT

```python
MAX_LOCATIONS_PER_CODE = 5
def create_mypy_prompt(result: MypyResult, max_issues: int | None = None) -> str | None: ...
def get_mypy_prompt(..., timeout_seconds: int = DEFAULT_CHECK_TIMEOUT, max_issues: int | None = None) -> str | None: ...
```
`get_mypy_prompt` forwards `max_issues` to `create_mypy_prompt`. The runner is unchanged.

`CheckerTools._format_mypy_result`: `None` → `"Mypy check completed. No type errors found."`,
otherwise return the prompt unchanged. Drop the `MYPY_FAILURE_PREFIX` check and import there.

## HOW

`from mcp_tools_py.utils.report_counts import format_dir_split, format_total_line, plural`.
The Summary block is removed.

## ALGORITHM

```
if not result.messages: return None
issues = [m for m in messages if m.severity != "note"]; notes = [m ... == "note"]
groups = by (m.code or "other"), sorted by (-len, code)
limit = len(groups) if max_issues is None else max(0, max_issues)
lines = (["Mypy found type issues that need attention:", ""] if issues else []) + [format_total_line("mypy", len(issues), len(groups)), ""]
detail groups[:limit]: f"**{code} ({plural(n,'issue')}) {split}**", 5 locations "- f:l:c - msg" + hint lines indented 4 spaces, "  ... and N more"
summary groups[limit:]: f"- {code}: {plural(n,'occurrence')} {split}"
if notes and (max_issues is None or max_issues > 0): "Notes:" + "- f:l:c - msg" (+ indented hint)
if issues: "To fix these issues:" footer (unchanged text)
```
The notes condition uses `max_issues`, not `limit`: a notes-only run has no groups, so `limit` is 0
even when `max_issues` is `None`.

## DATA

Notes-only run (`max_issues=None`):
```
mypy found 0 issues across 0 rules

Notes:
- src/a.py:9:1 - Revealed type is "builtins.int"
```
Notes-only with `max_issues=0`: `mypy found 0 issues across 0 rules`.

## Tests

- Default: wrapper header, then total line; every code detailed with 5 locations; codes ordered by
  count then name; split in headers; no `**Summary:**`; "To fix" footer present.
- `max_issues=1`: top code detailed, rest one summary line each with count and split.
- `max_issues=0` and negative: total line + summary lines only, no paths, no Notes.
- Hint lines appear indented under their error.
- Standalone notes in one `Notes:` section at the end, not counted in the total.
- Notes-only: starts with `mypy found 0 issues across 0 rules`, no wrapper header, no footer.
- Singular: `mypy found 1 issue across 1 rule`.
- Rewrite `test_create_mypy_prompt_with_messages`, `_many_messages_same_code`, `_summary_statistics`
  (Summary block gone).
- `test_checker_tools_formatting.py`: `_format_mypy_result` passes a report through unchanged;
  `None` still gives "No type errors found"; failure test still passes as-is.
