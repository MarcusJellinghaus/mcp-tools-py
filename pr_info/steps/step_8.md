# Step 8: Save or clear data from both callers

**Commit:** `feat(coverage): save each coverage run in the target project`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_8.md`. Implement step 8 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit. Also run `tests/test_pytest_tool_coverage.py` and `tests/test_toolkit_saved_coverage.py`, which the default marker selection skips.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/coverage_store.py`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `src/mcp_tools_py/toolkit.py`
- `docs/architecture/architecture.md`
- `tests/_coverage_project.py` (new: `_run_pytest_check` and the project builder moved out of `test_pytest_tool_coverage.py`)
- `tests/test_code_checker_pytest/test_coverage_store.py`
- `tests/test_toolkit_saved_coverage.py` (new)
- `tests/test_pytest_tool_coverage.py`

## WHAT

In `coverage_store.py`:

```python
@dataclass
class CoverageRun:
    project_dir: str
    temp_dir: str
    sources: list[str]     # resolved, normalized, sorted
    roots: list[str]
    hashes: dict[str, str]
    fail_under: float | None
    selection: str

@dataclass
class FinishedRun:
    data: dict[str, Any] | None
    selection: str
    outcome: RunOutcome
    notes: list[str]

def start_coverage_run(project_dir, temp_dir, test_folder, coverage_source, sources,
                       fail_under, selection) -> CoverageRun: ...
def finish_coverage_run(run: CoverageRun, data: dict[str, Any] | None,
                        report: PytestReport | None, verdict: RunVerdict) -> FinishedRun: ...
def view_of_runs(runs: list[dict[str, Any]]) -> tuple[str, RunOutcome]: ...
```

## HOW

`pytest_tool.py`:

- Build `selection` before the run, then call `start_coverage_run` right before `check_code_with_pytest`, passing the caller's raw `coverage_source` for the roots.
- After the run: `data = read_coverage_report(temp_dir) if report is not None else None`, then `finish_coverage_run(...)`.
- Digest: `format_coverage_digest(finished.data, finished.selection, max_modules=..., fail_under=..., **finished.outcome)`, or `no_report_message`.
- Append `finished.notes` to the digest, one per line.

`toolkit.py`:

- Move `verdict` and `report` reading up. Call `finish_coverage_run` immediately after `check_code_with_pytest`, before the three early returns, when `temp_dir` is set.
- Use `finished` in the digest at the end. Append notes to `raw` only on that path; `finish_coverage_run` logs failures, which covers the early returns.

`architecture.md`: add `coverage_store.py` under `code_checker_pytest` in the Module Overview, and `.mcp-tools-py/coverage/` as the storage location.

## ALGORITHM

```
finish: outcome = run_outcome(report, verdict)
    try:
        if data is None: clear_saved(project_dir)
        else: write_saved(project_dir, saved dict with one run entry, temp_dir/.coverage)
    except OSError as exc: logger.warning; note "Could not update saved coverage data: {exc}"
    return FinishedRun(data, run.selection, outcome, notes)
view_of_runs: join unique selection texts with " + " (keeping one "selection: " prefix),
    sum both counts, any() the flag
```

A run with no report and no parsed pytest report are the same case here, because the caller passes `data=None` for both.

## DATA

One run entry: `{"selection": ..., "data_file": None, **outcome}`. `write_saved` fills `data_file`. Step 11 adds `identity`.

## TESTS

`test_coverage_store.py`:

- `finish_coverage_run` with data writes the metadata, and with `None` clears it and returns the outcome.
- An `OSError` during write or clear gives one note and doesn't raise.
- `view_of_runs`: one run; two runs sum counts; identical selection lines dedupe; `generic_warning` is any.

`test_toolkit_saved_coverage.py`, `integration`, real projects via `tests/_coverage_project.py`:

- All three early returns update saved data: `No Tests Found` clears it; a failing collector under `-n 2` (ERROR with a report and JSON) saves it; a mocked `FAILED` verdict with no findings saves it.
- Quick and standard depths leave saved data alone.

`test_server_params.py` stays as it is: its mocks produce no `.coverage` file, and `write_saved` tolerates that, writing into `tmp_path`.

`test_pytest_tool_coverage.py`:

- Rewrite `test_coverage_leaves_the_project_clean`: `git init` in the project (skip when `shutil.which("git")` is `None`), run with `coverage=True`, assert `.mcp-tools-py/coverage/last_run.json` exists and `git status --porcelain --untracked-files=all` mentions neither `.mcp-tools-py` nor `coverage.json` nor `.coverage ` at the root.
- A run without coverage leaves the saved data untouched.
- A run with `extra_args=["-k", "nomatch"]` says `Coverage report was not produced.` and clears the saved data.
