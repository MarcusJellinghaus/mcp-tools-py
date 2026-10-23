# Step 1 — `resolve_source_directories`

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_1.md`. Write the tests first, then the code. Run the checks listed in the summary and commit once.

## WHERE

- `src/mcp_tools_py/utils/project_config.py`
- `tests/test_project_config.py` (next to the existing `resolve_coverage_source` tests, around line 607)

## WHAT

```python
def _resolve_source_dirs(
    project_dir: str, explicit: list[str] | None, label: str, arg_name: str
) -> list[str] | str: ...

def resolve_source_directories(
    project_dir: str, target_directories: list[str] | None
) -> list[str] | str:
    return _resolve_source_dirs(project_dir, target_directories, "source directories", "target_directories")

def resolve_coverage_source(
    project_dir: str, coverage_source: list[str] | None
) -> list[str] | str:
    return _resolve_source_dirs(project_dir, coverage_source, "coverage source", "coverage_source")
```

## HOW

Move the current body of `resolve_coverage_source` into `_resolve_source_dirs`, replacing the two hard-coded strings with `label` and `arg_name`. `resolve_coverage_source` keeps its docstring and produces exactly the same output as before.

## ALGORITHM

```
if explicit is not None: return explicit
try: toml = _load_pyproject(project_dir) except ValueError as exc: return f"Error resolving {label}: {exc}"
src, tests = _read_source_dirs(...), _read_test_dirs(...); log warnings
keep = [s for s in src if (root/s).is_dir() and no test path is inside s]
if keep: return keep
return f"Error resolving {label}: no source directory outside the test paths (source: {src}, tests: {tests}). Pass {arg_name} explicitly."
```

## DATA

A list of project-relative directory names, or one error string.

## Tests (write first)

- The existing `resolve_coverage_source` tests still pass unchanged.
- `resolve_source_directories`:
  - explicit list is returned as-is
  - default `["src"]` with tests excluded
  - a source dir that contains the test path is dropped, and an error results when nothing is left
  - invalid TOML gives an error
  - the error strings start with `"Error resolving source directories:"`, the nothing-left error contains `"Pass target_directories explicitly."`, and neither error contains `"coverage"`.
