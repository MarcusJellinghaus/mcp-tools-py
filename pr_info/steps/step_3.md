# Step 3 — Ruff report: total line, rule names, directory split

## LLM prompt

Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_3.md`) only.
Tests first. Run pylint, pytest (`-n auto`), mypy; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_ruff/reporting.py` — `format_ruff_check_report`, new `_rule_label`
- `src/mcp_tools_py/checker_tools/ruff_check_tool.py` — docstring only
- `tests/test_code_checker_ruff/test_reporting.py`

## WHAT

```python
def _rule_label(code: str, url: str | None) -> str: ...
def format_ruff_check_report(messages: List[RuffMessage], max_issues: int = 1) -> Optional[str]: ...  # unchanged signature
```

## HOW

`from mcp_tools_py.utils.report_counts import format_dir_split, format_total_line, plural`.
Grouping and sort order (`group_and_sort_issues`) unchanged. `format_ruff_fix_report` untouched.

## ALGORITHM

```
_rule_label: name = url.rstrip("/").rsplit("/", 1)[-1] if url else ""; return f"{code} {name}".strip()
sections = [format_total_line("ruff", len(messages), len(groups))]
for group in groups[:max_issues]:
    header = f"ruff found {plural(n, 'issue')} with rule {label} {split}."   # replaces URL
    then message, "Locations:", capped locations, overflow line (as today)
summary: "- {label}: {plural(n, 'occurrence')} {split}" for remaining groups
```
`split = format_dir_split(m.filename for m in group.messages)`.

## DATA

`max_issues=0` example:
```
ruff found 143 issues across 8 rules

- SIM117 multiple-with-statements: 119 occurrences (tests: 119)
- SIM102 collapsible-if: 13 occurrences (src: 11, tests: 2)
```

## Docstring

`max_issues: Number of issue types shown in detail (default: 1). 0 = counts only: one line per rule
with count and directory split, no file paths.`

## Tests

- Total line is the first line (singular form with one finding).
- `max_issues=0`: total line + one line per rule with name and split, no `:line:col` paths.
- Detailed header shows the name, not the URL, and the split.
- `url=None` / `""` (e.g. `invalid-syntax`) → code only.
- Root file → `(root)`; absolute path on another drive (as left by the parser) → `(outside)`.
- Update existing assertions for the old header/summary wording.
