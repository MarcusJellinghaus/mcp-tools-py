# Step 13 — Toolkit `fix_text`

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_13.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- `src/mcp_tools_py/toolkit_checks.py` (`_result_from_findings`, `_merge`, new `_render_fix_text`)
- New test: `tests/test_toolkit_fix_text_budget.py`; update the tests asserting exact
  `fix_text` bullets (`tests/test_toolkit_check*.py`, `tests/test_toolkit_test.py`,
  `tests/test_toolkit_format.py`)

## WHAT
```python
FIX_TEXT_HINT = "Fix these and rerun the check to see the rest."

def _render_fix_text(findings: list[Finding], locations: list[str | None]) -> str: ...
def _result_from_findings(...same signature...) -> ActionResult   # fix_text = bounded _render_fix_text
def _merge(results: list[ActionResult]) -> ActionResult           # per-result budget split
```
`_finding_line` stays (used by `_run_mypy`).

## HOW
- `_render_fix_text`: group findings by `rule` (or `""`), with groups ordered by count
  descending. Each group gets a line `"{rule} ({plural(n,'finding')}) {format_dir_split(paths)}"`
  (just `"{n} findings"` when there is no rule), then
  `render_locations([Location(path, line, finding.message) ...], hint=FIX_TEXT_HINT)`.
  `path`/`line` come from the location string: `rsplit(":", 1)` when the right part is
  digits, else `(location or finding.path, None)`. Pytest node IDs stay whole.
- `_result_from_findings`: `fix_text = bound_text(_render_fix_text(...), hint=FIX_TEXT_HINT)`.
  This covers check (pylint, ruff, bandit, deptry, and vulture/tach after steps 10–11),
  test and format.
- `_merge`: `parts` as today. Let `n` = the number of non-empty parts. Each part becomes
  `bound_text(part, TOOL_LINES // n, TOOL_CHARS // n, hint=FIX_TEXT_HINT)`. Join them,
  then apply `bound_text(joined, hint=FIX_TEXT_HINT)` as a backstop. Every check depth
  goes through `_merge`, so mypy's direct `fix_text` and lint-imports' report are bounded
  here too.
- Finding keys and `findings` lists are never touched.

## ALGORITHM
```
groups = defaultdict(list) by finding.rule; order by -len
lines = []; for rule, items in groups: lines += [group header, *render_locations(items, FIX_TEXT_HINT)]
fix_text = bound_text("\n".join(lines), hint=FIX_TEXT_HINT)
_merge: parts = non-empty fix_texts; n = len(parts); parts = [bound_text(p, TOOL_LINES // n, TOOL_CHARS // n, hint) ...]
fix_text = bound_text("\n".join(parts), hint=FIX_TEXT_HINT)
```

## DATA
`ActionResult.fix_text` ≤ `TOOL_LINES` lines / `TOOL_CHARS` chars.

## Tests (write first)
- 1500 pylint findings → `fix_text` ≤ `TOOL_LINES` lines, `len(findings) == 1500`, keys unchanged.
- `_merge` of 8 results, each with 1000-line fix_text → bounded, and each of the 8 tools'
  first group header is present (every tool represented).
- Pytest findings (node IDs as locations) render one row per failing test with its message.
