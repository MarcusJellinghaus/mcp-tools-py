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

def _render_fix_text(
    findings: list[Finding],
    locations: list[str | None],
    details: list[tuple[str, ...]] | None = None,   # parallel to findings; Location.details
) -> str: ...
def _result_from_findings(...same signature...) -> ActionResult   # fix_text = bounded _render_fix_text
def _merge(results: list[ActionResult]) -> ActionResult           # per-result budget split
```
`_finding_line` stays only for `_merge`'s fallback part (results with findings but no
`fix_text`); delete it if that fallback no longer needs it.

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
- `_run_mypy` (`toolkit_checks.py:170` setter): replace the flat `_finding_line` +
  `format_hint_lines` join with
  `bound_text(_render_fix_text(findings, locations, details=[tuple(format_hint_lines(m.hint)) for m in issues]), hint=FIX_TEXT_HINT)`,
  with `locations = [f"{m.file}:{m.line}" if m.line >= 0 else None for m in issues]`.
  mypy's `fix_text` is thus grouped by code and capped at its own setter, not left to
  `_merge`'s head/tail cut. `render_locations` prints each row's first item's details,
  and `format_hint_lines` already caps hints at `HINT_LINES` (step 6).
- `_merge`: `parts` as today. Let `n` = the number of non-empty parts. Each part becomes
  `bound_text(part, TOOL_LINES // n, TOOL_CHARS // n, hint=FIX_TEXT_HINT)`. Join them,
  then apply `bound_text(joined, hint=FIX_TEXT_HINT)` as a backstop. lint-imports' report
  (already bounded by step 9) is split here too.
- Finding keys and `findings` lists are never touched.

## ALGORITHM
```
items = [Location(path, line, f.message, details[i] if details else ()) for i, f in enumerate(findings)]
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
- `_run_mypy` with 1500 errors in 5 codes, each with an 8-line hint (patch
  `run_mypy_check`): its own `ActionResult.fix_text` (before `_merge`) is ≤ `TOOL_LINES`
  lines, has one header per code, shows indented hint lines under a row, ends with
  `FIX_TEXT_HINT`, and `len(findings) == 1500`.
