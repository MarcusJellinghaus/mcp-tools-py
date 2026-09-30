# Step 4 — Pylint report: total line, symbol, count and directory split

## LLM prompt

Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_4.md`) only.
Tests first. Run pylint, pytest (`-n auto`), mypy; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_pylint/reporting.py` — `get_pylint_prompt`,
  `get_prompt_for_known_pylint_code`, `get_prompt_for_unknown_pylint_code`
- `src/mcp_tools_py/checker_tools/pylint_tool.py` — docstring only
- `tests/test_code_checker_pylint/test_reporting.py`

## WHAT

```python
def get_prompt_for_known_pylint_code(code: str, project_dir: str, pylint_results: PylintResult, header: str) -> Optional[str]: ...
def get_prompt_for_unknown_pylint_code(code: str, project_dir: str, pylint_results: PylintResult, header: str) -> str: ...
```
`header` replaces each prompt's first line (`pylint found some issues related to code X ...`).
The unknown prompt's instruction lines (which name code and symbol) stay.

## HOW

`from mcp_tools_py.utils.report_counts import format_dir_split, format_total_line, plural`.
Split uses `normalize_path(msg.path, project_dir)`; `Command line` passes through and counts as
`(outside)`. Grouping and severity sort unchanged.

## ALGORITHM

```
split(g) = format_dir_split(normalize_path(m.path, project_dir) for m in g.messages)
line(g)  = f"- {g.message_id} {g.symbol}: {plural(n, 'occurrence')} {split(g)}"
out = [format_total_line("pylint", total_occurrences, len(groups))]
max_issues == 0: out += [line(g) for g in groups] + footer "Use max_issues>=1 ..."; return
for g in groups[:max_issues]: header = f"pylint found {plural(n,'issue')} with rule {g.message_id} {g.symbol} {split(g)}."
    prompt = known(..., header) or unknown(..., header); append overflow line as today
remaining: "--- N additional issue types ---" block using line(g), plus "Use max_issues=..." hint (kept)
```
The header is built from the full group, so the count is the true total even though the prompt
receives the capped result.

## DATA

`max_issues=0`:
```
pylint found 7 issues across 2 rules

- E0602 undefined-variable: 3 occurrences (src: 3)
- W0613 unused-argument: 4 occurrences (src: 3, tests: 1)

Use max_issues>=1 to see details for one or more issue types.
```

## Docstring

`max_issues: ... 0 = counts only: one line per rule with count and directory split, no file paths.`

## Tests

- Total line first in `max_issues=0` and `max_issues>=1` modes; singular wording for one issue.
- `max_issues=0`: names and splits, no JSON location blocks, footer kept.
- Known-code detail (e.g. `W0612`) header contains count, symbol and split; unknown-code header too.
- Header count is the full count when locations are capped at 50.
- `Command line` path counts as `(outside)`.
- Rewrite `test_max_issues_zero_stats_only` (old `2 issue types` / `7 total occurrences` header) and
  summary-line assertions for the new format.
