# Step 5 — Bandit report: total line, test names, directory split

## LLM prompt

Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_5.md`) only.
Tests first. Run pylint, pytest (`-n auto`), mypy; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_bandit/reporting.py` — `format_bandit_report`
- `src/mcp_tools_py/checker_tools/bandit_tool.py` — docstring only
- `tests/test_code_checker_bandit/test_reporting.py`

## WHAT

Signature unchanged: `format_bandit_report(messages, errors, max_issues=1) -> str | None`.

## HOW

`from mcp_tools_py.utils.report_counts import format_dir_split, format_total_line, plural`.
Sort order and the CWE line (as changed by #236) unchanged.

## ALGORITHM

```
groups = group_and_sort_issues(messages)
if not groups and not errors: return None
sections = [format_total_line("bandit", len(messages), len(groups))]
if errors: sections.append("File errors (files not scanned):" + lines)
detail header: f"bandit found {plural(n,'issue')} with {test_id} {test_name} {split} [severity: .., confidence: ..]"
summary line:  f"- {test_id} {test_name} ({severity}): {plural(n,'occurrence')} {split}"
```

## DATA

Errors-only run:
```
bandit found 0 issues across 0 rules

File errors (files not scanned):
- bad.py: syntax error
```

## Docstring

`max_issues: ... 0 = counts only: one line per rule with count and directory split, no file paths.`

## Tests

- Total line first, before File errors; errors-only run prints `bandit found 0 issues across 0 rules`.
- `max_issues=0`: one line per test id with `test_name` and split, no `file:line` paths.
- Detail header contains `test_name` and split; singular wording for one issue.
- Update existing header/summary assertions.
- `tests/test_code_checker_bandit/test_reporting.py:167`: the ordering check uses
  `result.index("bandit found")`, which now matches the total line before "File errors". Look up the
  detail header (e.g. `"bandit found 1 issue with"`) instead.
