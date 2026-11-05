# Step 11: Add `combine_with_previous`

**Commit:** `feat(coverage): combine partial coverage runs`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_11.md`. Implement step 11 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit. Also run `tests/test_pytest_tool_combine.py`, which the default marker selection skips.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/coverage_store.py`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `src/mcp_tools_py/toolkit.py`
- `README.md`
- `tests/test_code_checker_pytest/test_coverage_store.py`
- `tests/test_pytest_tool_combine.py` (new)

## WHAT

`CoverageRun` gains `identity: str`, `interpreter: str`, `env_vars: dict[str, str] | None`, `timeout_seconds: int` and `combine: bool = False`. `start_coverage_run` takes them. Run entries gain `"identity"`, `load_saved` adds it to the keys each run entry must have, and it still treats a missing top-level key as no saved run.

`run_pytest_check` gains `combine_with_previous: bool = False`, documented in the docstring.

```python
def _mismatch_reason(saved: dict[str, Any], run: CoverageRun) -> str | None: ...
```

## HOW

`pytest_tool.py`:

- Add `("combine_with_previous", combine_with_previous)` to the reuse conflict list.
- After the reuse block, and still before the gates: `if combine_with_previous and not coverage: return "Error: combine_with_previous=True requires coverage=True."`.
- Pass `env_vars` (the caller's, without `COVERAGE_FILE`), `context.resolve_timeout("pytest", timeout_seconds)` and `selection_identity(...)` to `start_coverage_run`.

`toolkit.py`: pass `selection_identity(markers, [], [], addopts, None)` and leave `combine=False`, so `full` depth always replaces the set, but a later `combine_with_previous=True` can still merge with what it saved.

`README.md`: add the parameter to the table and describe merging, including that it's opt-in, and which conditions discard saved runs.

## ALGORITHM

```
finish, in order:
  no data: combine -> leave the store alone, note "Saved coverage data was not changed."
           else clear_saved
  entry = new run; runs = [entry]; final = data
  saved = load_saved() if run.combine else None
  if saved: reason = _mismatch_reason(saved, run)
    reason -> note "Saved runs discarded: {reason}."
    else previous = saved runs with a different identity
      any previous with data_file None -> missing input: no merge call, note "Saved runs discarded: merging failed."
      else previous -> merged = merge_coverage_data(previous data files, joined to the store directory, + temp_dir/.coverage)
        None -> note "Saved runs discarded: merging failed."
        else final = merged; runs = previous + [entry]
  write_saved(final, runs); selection, outcome = view_of_runs(runs)
_mismatch_reason: saved["sources"] != run.sources -> "coverage_source changed"
    saved["hashes"] != run.hashes -> "files changed since the saved runs"
    hash_python_files(now) != run.hashes -> "files changed during this run"
```

With no saved set, or when the only saved run has the same identity, it behaves like a plain run with no note. `write_saved` must keep the data files of `previous`: they're referenced by `runs`, so its cleanup leaves them.

## DATA

`FinishedRun.data` is the merged report, `selection` lists every merged selection, and `outcome` holds the summed counts, so the digest and a later reuse agree. Merge failure and mismatch use the same note format.

## TESTS

`test_coverage_store.py`, unit, with `merge_coverage_data` patched:

- `_mismatch_reason`, parametrized: same inputs give `None`; sources differ; saved hashes differ; hashes differ now (an edit during the run).
- `None` and an equivalent explicit list compare equal, since `sources` is resolved, normalized and sorted.
- A failed merge saves only the new run, with a note, and the old data files are deleted.
- A saved run with `data_file: None` counts as a failed merge: `merge_coverage_data` isn't called, only the new run is saved, the note is added, and nothing raises.
- No report with `combine=True` leaves the metadata byte-identical and adds the note; with `combine=False` it clears.
- A rerun of an identical selection replaces its entry, without merging when it was the only one.
- A replaced selection's counts drop out of the sum, and the same collector count in two selections adds up.
- First combine with no saved set: no note.

`test_pytest_tool_combine.py`:

- Unit: `combine_with_previous=True` without `coverage=True` is refused and pytest never runs. `use_last_coverage_run=True` with `combine_with_previous=True` is refused.
- `integration`, real project via `tests/_coverage_project.py`:
  - Two selections via `extra_args` merge: the percentage is higher than either alone, and the selection line lists both.
  - Editing a source between runs gives the discarded note and doesn't merge.
  - A different `coverage_source` does the same.
  - Reuse after a merge returns the merged set, with summed warning counts.
  - A configured `fail_under` doesn't fail the merge.
  - A `-k nomatch` run with `combine_with_previous=True` leaves the set unchanged and says so.
  - A rerun of an identical selection replaces it: rerunning after the set holds two selections keeps two entries.
  - Toolkit `full` depth after a merge replaces the set with one run.
