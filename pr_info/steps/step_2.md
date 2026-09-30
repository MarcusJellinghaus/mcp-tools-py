# Step 2 — Source-only lookup for `coverage_source`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_2.md`).
> Implement only this step, TDD: write the tests first, then the code. Run
> pylint, pytest (`-n auto`), mypy and `run_format_code`; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/utils/project_config.py`
- `tests/test_project_config.py`

## WHAT

```python
def _read_source_dirs(toml_data: dict[str, object], warnings: list[str]) -> list[str]
def _read_test_dirs(toml_data: dict[str, object], warnings: list[str]) -> list[str]

def resolve_coverage_source(
    project_dir: str, coverage_source: list[str] | None
) -> list[str] | str:
    """Explicit list as-is; else existing source dirs that contain no testpath,
    or an error string naming `coverage_source`."""
```

## HOW

- Extract the two existing parsing blocks of `get_target_directories` into
  `_read_source_dirs` / `_read_test_dirs` (same fallbacks `["src"]` / `["tests"]`,
  same warning texts). `get_target_directories` calls them; its behaviour and
  existing tests stay unchanged. Load via `_load_pyproject` from step 1.
- Warnings are logged with `logger.warning`, as `resolve_target_directories` does.
- Error string convention mirrors `resolve_target_directories`
  (`"Error resolving …: …"`).

## ALGORITHM (decision 17 — containment, not set subtraction)

```
if coverage_source is not None: return coverage_source
data = _load_pyproject(project_dir)          # ValueError -> error string
src, tests = _read_source_dirs(...), _read_test_dirs(...)
keep = [s for s in src if isdir(project/s)
        and not any(is_relative_to(resolve(project/t), resolve(project/s)) for t in tests)]
return keep or "Error resolving coverage source: no source directory outside the test paths (…). Pass coverage_source explicitly."
```

`Path.is_relative_to` is true for equal paths too, so `where = ["tests"]` is dropped as well.

## DATA

`["src"]` or `"Error resolving coverage source: …coverage_source…"`.

## Tests

- `where=["src"]`, `testpaths=["tests"]` → `["src"]`
- `where=["."]`, `testpaths=["tests"]` → error string containing `coverage_source`
- non-existent source dir dropped; all dropped → error string
- explicit `coverage_source` returned unchanged (no pyproject needed)
- `get_target_directories` existing tests still pass
