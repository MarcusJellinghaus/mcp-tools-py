# Step 6: Collapse the zero-coverage list; `max_modules` controls only the ranking

**Commit:** `feat(coverage): collapse uncovered directories in the digest`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_6.md`. Implement step 6 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/coverage.py`
- `src/mcp_tools_py/checker_tools/pytest_tool.py` (docstring)
- `README.md`
- `tests/test_code_checker_pytest/test_coverage.py`
- `tests/test_code_checker_pytest/test_coverage_zero_list.py` (new)

## WHAT

```python
MAX_ZERO_COVERAGE_ROWS = 15

def _zero_coverage_rows(files: dict[str, Any]) -> list[tuple[str, int]]: ...  # (label, missing)
```

## HOW

- The zero-coverage section of `format_coverage_digest` uses these rows and this cap. `max_modules` no longer touches it.
- The header keeps counting modules: `{len(zero)} modules have no covered statements in this selection:`. `… and N more` counts rows.
- Keep the `N further modules have gaps` line, including at `max_modules=0`.
- Docstrings of `format_coverage_digest` and `run_pytest_check`, and `README.md:72`: `max_modules` is how many modules the gap ranking details, and `0` shows only the overview.

## ALGORITHM

```
prefix = _common_prefix(files)
blocked = every ancestor directory of a file with covered_lines > 0
for each zero file (statements > 0, covered_lines == 0):
    walk its ancestors from prefix downward; stop at the root directory, which is never a row
    label = first ancestor not in blocked, as "a/b/"; else the file's normalized path
    a file outside prefix gets its own row
sum missing per label; sort by (-missing, label)
```

0-statement files neither block nor appear.

## DATA

```
224 modules have no covered statements in this selection:
    src/pkg/cli/ (5400 missing statements)
    src/pkg/workflows/runner.py (310 missing statements)
    … and N more
```

## TESTS

In `test_coverage_zero_list.py`, in a `TestZeroCoverageList` class, using the helpers from `_coverage_report.py`:

- A fully uncovered directory is one row, with summed missing statements.
- A directory with one covered file doesn't collapse; its zero files are listed individually.
- A directory whose `__init__.py` has covered statements doesn't collapse.
- A 0-statement `__init__.py` doesn't stop a collapse.
- A nested uncovered directory collapses to its top-most uncovered ancestor, and a fully uncovered tree collapses to the common prefix, not above it.
- Rows are sorted by missing statements.
- 20 uncovered directories: 15 rows, `… and 5 more`, and the header's module count is unaffected.
- No cause is attributed: `untested`, `not selected` and `never traced` don't appear.
- A synthetic 250-module project over 12 packages at `max_modules=0` has at most 40 lines in total.
- `max_modules=0` shows the package table and the zero-coverage list, and no gap ranking.

In `test_coverage.py`, update `test_max_modules_zero` (`:362`): `z.py` now appears, `a.py` doesn't, `… and 1 more` is gone, and `1 further modules have gaps` stays.

The existing test at `:346` (`    probe.py (150 missing statements)`) keeps passing, because a file at the project root gets its own row.
