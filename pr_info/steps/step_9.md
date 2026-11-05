# Step 9: Add `use_last_coverage_run`

**Commit:** `feat(coverage): reuse the last coverage run`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_9.md`. Implement step 9 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit. Also run `tests/test_pytest_tool_reuse.py`, which the default marker selection skips.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/coverage_store.py`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `README.md`
- `tests/test_code_checker_pytest/test_coverage_store.py`
- `tests/test_pytest_tool_reuse.py` (new)

## WHAT

In `coverage_store.py`:

```python
def format_last_run(project_dir: str, coverage_source: list[str] | None, max_modules: int) -> str: ...
def narrow_files(files: dict[str, Any], measured: list[str], paths: list[str]) -> dict[str, Any] | str: ...
```

`run_pytest_check` gains `use_last_coverage_run: bool = False`, documented in the docstring.

## HOW

The reuse branch is the first thing in `run_pytest_check`, before the `pytest` and `pytest-cov` gates:

```python
if use_last_coverage_run:
    conflicts = [name for name, given in (
        ("markers", bool(markers)), ("extra_args", bool(extra_args)),
        ("env_vars", bool(env_vars)), ("timeout_seconds", timeout_seconds is not None),
        ("coverage", coverage),
    ) if given]
    if conflicts:
        return f"Error: use_last_coverage_run=True cannot be used with: {', '.join(conflicts)}."
    return format_last_run(project_dir, coverage_source, max_modules)
```

Reuse only reads, so a read-only project works. `README.md`: add the parameter to the table and a paragraph with the documented limits: config changes aren't checked, and a root `conftest.py`, path arguments outside the test directories and package-name sources sit outside the hash scope. Also state that `.mcp-tools-py/coverage/` holds the data and ignores itself.

## ALGORITHM

```
format_last_run: saved = load_saved(); None -> message telling the caller to run with coverage=True
    hash_python_files(project_dir, saved["roots"]) != saved["hashes"] -> "stale — rerun ..." with no numbers
    files = saved["report"]["files"]; narrow when coverage_source is non-empty; str result -> return it
    selection, outcome = view_of_runs(saved["runs"])
    return format_coverage_digest({"files": files}, selection, max_modules=max_modules,
                                  fail_under=saved["fail_under"], **outcome)
narrow_files, per path: compare norm_path components, with "." as ()
    path strictly contains a measured source -> refuse
    no file key under path -> refuse, naming the path and asking for a directory under the measured sources
    keep the union of files under the paths
```

## DATA

Messages:

- `No saved coverage run. Run with coverage=True first.`
- `stale — rerun: N files changed since the last coverage run. Run with coverage=True.`

## TESTS

`test_coverage_store.py`, unit level:

- `narrow_files`, parametrized: a sub-path keeps only its files; a path equal to a measured source is allowed; `src/pk` doesn't match `src/pkg` (whole components); `.` and a parent of a source are refused; a package name is refused; an absolute path is refused; backslash paths and Windows-style keys match.
- `format_last_run` on written metadata: a narrowed header shows totals for the narrowed files only, with branch data included in the percentage; repeats the saved selection line and warning lines, including the generic warning.
- Corrupt metadata reads as no saved run.

`test_pytest_tool_reuse.py`:

- Unit, with `check_code_with_pytest` patched: parametrized refusal of each conflicting argument, naming it; empty `[]` and `{}` and `timeout_seconds=None` are allowed; pytest never runs; works with `pytest` reported unavailable (gate order).
- `integration`, real project via `tests/_coverage_project.py`: run with `coverage=True`, then reuse returns the digest; editing, adding or deleting a source or test `.py` returns `stale — rerun` with no `stmts` in the reply; with no saved run the reply names `coverage=True`; `max_modules=0` applies; an out-of-scope `coverage_source` is refused.
