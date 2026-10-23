# Step 4 — `code_checker_deptry/reporting.py`: the digest

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_4.md`. Write the tests first, then the code. Use `code_checker_ruff/reporting.py` as the model. Run the checks listed in the summary and commit once.

## WHERE

- `src/mcp_tools_py/code_checker_deptry/reporting.py` (new)
- `src/mcp_tools_py/code_checker_deptry/__init__.py` (re-export `format_deptry_report`)
- `tests/test_code_checker_deptry/test_reporting.py` (new)

## WHAT

```python
MAX_LOCATIONS_PER_ISSUE: int = 50

def format_deptry_report(messages: list[DeptryMessage], max_issues: int = 1) -> str | None: ...
def _location(msg: DeptryMessage) -> str: ...
```

## HOW

Use `format_total_line`, `format_dir_split` and `plural` from `mcp_tools_py.utils.report_counts`. Sections are joined with `"\n\n"`, as in ruff.

## ALGORITHM

```
if not messages: return None
groups = messages grouped by code, sorted by (-len(group), code); max_issues = max(0, max_issues)
sections = [format_total_line("deptry", len(messages), len(groups))]
for code, msgs in groups[:max_issues]: header f"deptry found {plural(n,'issue')} with rule {code} {split}." + "Locations:" + capped _location lines + "... and K more occurrences"
remaining: one line each f"- {code}: {plural(n,'occurrence')} {split}"
```

`_location`: when `msg.line is None`, return `f"- {msg.file}: '{msg.module}'"` (the DEP002 form, e.g. `- pyproject.toml: 'requests'`). Otherwise return `f"- {msg.file}:{msg.line}:{msg.column} {msg.module} {msg.message}"`.

`split` is `format_dir_split(m.file for m in msgs)`. `pyproject.toml` therefore counts as `(root)`.

## DATA

A report string, or `None` when there are no messages.

## Tests (write first)

- Empty list → `None`.
- The total line reads `deptry found 3 issues across 2 rules`.
- The most frequent code is detailed first; ties are broken by code.
- A detail entry has the form `- src/a.py:3:1 yaml '...message...'`.
- A DEP002 entry reads `- pyproject.toml: 'requests'`.
- The directory split appears in the header and in summary lines, e.g. `(src: 2)` and `(root: 1)`.
- `max_issues=0` gives only the total line plus one count line per code, with no file paths.
- `max_issues` larger than the number of groups details them all.
- More than 50 locations gives the overflow line.
