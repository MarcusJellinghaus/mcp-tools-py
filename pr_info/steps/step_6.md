# Step 6 — Coverage digest formatter

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_6.md`).
> Implement only this step, TDD: write the tests first, then the code. Run
> pylint, pytest (`-n auto`), mypy and `run_format_code`; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/coverage.py`
- `tests/test_code_checker_pytest/test_coverage.py`

## WHAT

```python
MAX_FUNCTIONS_PER_MODULE = 3   # decision 15
MAX_RANGES_PER_FUNCTION = 5
MODULE_LEVEL = "<module level>"

def format_coverage_digest(
    data: dict[str, Any],
    selection: str,
    max_modules: int = 10,
    fail_under: float | None = 0.0,
    tests_failed: bool = False,
) -> str:
    """Render the coverage JSON as the digest appended to the pytest reply."""

def _ranges(lines: list[int]) -> list[str]:
    """Collapse sorted line numbers into "a-b" / "a" strings."""
```

## HOW

Input is coverage's JSON (`--cov-report=json`): `totals` and `files`; each file
has `summary` (`num_statements`, `covered_lines`, `missing_lines`,
`percent_covered`), `missing_lines`, and from coverage 7.6.0 a `functions` map
(region name → `{"missing_lines": [...], ...}`, methods pre-qualified, `""` =
module-level code). Use only `functions` (it covers every line; `classes` would
duplicate). Never parse the text table.

Output layout follows the issue's *Output* section.

## ALGORITHM

```
header: "{pct:.1f}%  {stmts} stmts  {missed} missed  |  {n} modules measured", then selection
if fail_under is None: "fail_under: could not be read from the coverage config"
elif fail_under > 0: f"fail_under={fail_under:g} is configured; not applied to this run"
if tests_failed: "Warning: tests failed; these numbers come from a run with failures."
zero = files with covered_lines == 0 and num_statements > 0      # no cause attributed
gaps = files with missing > 0 and covered > 0, sorted by (-missing, path)
for each of gaps[:max_modules]: "path  N missing  (P%)" then top 3 regions by
    len(missing_lines) (>0): name or MODULE_LEVEL, first 5 _ranges + ", …" if more;
    no `functions` key → one line of file-level ranges (first 5) from the file's missing_lines; set degraded
if degraded: "Per-function detail needs coverage >= 7.6.0; showing file-level ranges."
zero list: "{k} modules have no covered statements in this selection:" then
    "    path (N missing statements)" for zero[:max_modules], "… and M more" if cut
tail: "{len(gaps)-max_modules} further modules have gaps (use max_modules to see more)." when > 0
```

`max_modules` is clamped with `max(0, max_modules)` as in the `max_issues` pattern.
Default 10 differs from `max_issues=1` deliberately (issue).

## DATA

Returns a multi-line `str`; the empty-gaps case says
`"No uncovered statements in the measured modules."`.

## Tests (hand-built JSON dicts)

- header and selection line always present
- ranking by absolute missing, not percent (2000-stmt/90% ranks above 30-stmt/50%)
- `""` region rendered as `<module level>`, never an empty name
- caps: 4th function omitted; 6th range replaced by `…`
- zero-coverage modules excluded from ranking, listed with missing counts, no cause wording
- `max_modules` cut + tail line; `max_modules=0` shows header and counts only
- file without `functions` → file-level ranges + one degradation note
- `fail_under` 0.0 → no line; 80.0 → "not applied" line; `None` → "could not be read"
- `tests_failed=True` → warning line
- `_ranges([1,2,3,5,7,8])` → `["1-3", "5", "7-8"]`
