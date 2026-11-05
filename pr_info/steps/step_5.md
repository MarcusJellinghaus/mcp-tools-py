# Step 5: Compute totals from `files`; add the package table

**Commit:** `feat(coverage): add a per-package table to the digest`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_5.md`. Implement step 5 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/coverage.py`
- `tests/test_code_checker_pytest/test_coverage.py`

## WHAT

```python
def norm_path(path: str) -> str: ...   # "\\" -> "/", then posixpath.normpath
def percent_covered(summaries: Iterable[dict[str, Any]]) -> float: ...
def _common_prefix(files: dict[str, Any]) -> tuple[str, ...]: ...
def _package_table(files: dict[str, Any]) -> list[str]: ...
```

## HOW

- `format_coverage_digest` stops reading `data["totals"]`. The header sums `num_statements` and `missing_lines` from `files`, and takes the percentage from `percent_covered`.
- The table goes after the selection and `fail_under` lines, preceded by a blank line, and before the gap ranking.
- Report keys are printed as they are in the gap ranking. `norm_path` is only for comparing and grouping here, and steps 6 and 9 reuse it.

## ALGORITHM

```
percent: covered = Σ(covered_lines + covered_branches), total = Σ(num_statements + num_branches)
    missing keys count as 0; total == 0 -> 100.0
prefix: longest common leading directories of all non-__init__.py files; () if there are none
row(file): rest = parts after prefix, when the file is under prefix
    rest has a directory -> row is rest[0]; anything else, including outside prefix -> "(root)"
sum per row; skip rows with 0 statements; sort by (-missing, name)
```

## DATA

```
by package (statements, covered %):
    cli          6200   0%
    (root)        120   0%
```

Pad names to the longest name. The header line itself keeps its format.

## TESTS

In `test_coverage.py`, in a new `TestPackageTable` class:

- A src layout gets one row per subpackage, sorted by missing statements.
- A `src/__init__.py` with statements doesn't collapse the table to one row, and its statements land in `(root)`.
- Files directly in the package get a `(root)` row.
- Windows-style keys (`src\\pkg\\a\\m.py`) group the same as POSIX keys.
- Prefixes match on whole components: `src/pkg_a/` and `src/pkg_b/` give two rows, with prefix `src`.
- Parametrized `percent_covered`: lines only; with branches (5 of 11 gives 45.45, not the lines-only figure); zero denominator gives 100.0.
- `format_coverage_digest` on `{"files": ...}` with no `totals` key gives the right header.
- An empty `__init__.py` adds no `(root)` row.

Existing tests should keep passing, since `_report` and `_COVERAGE_DATA` have totals consistent with their files.
