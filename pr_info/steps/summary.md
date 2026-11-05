# Issue #252: Coverage digest: qualify partial runs, group collector errors, add package view, reuse and combine runs

The issue body is authoritative for behaviour. These files fix the structure, the order and the choices the issue leaves open. Where a step quotes the issue's wording, keep that wording.

## Goals

- A run with collection failures is reported as such: errors grouped by cause and counted, and no false "tests failed" text.
- The digest states up front how partial the run was, and adds a per-package view and a zero-coverage list that can be read in full.
- A coverage run can be drilled into without rerunning tests (`use_last_coverage_run`), and partial runs can be merged (`combine_with_previous`).
- Subprocess code is traced in this repo.

## Architectural and design changes

**Collector errors have one code path.** `reporting.py` gains the grouping helper. Both the ERROR path (`verdict._merge_problems`) and the FAILED path (`reporting._process_failed_collectors`) use it. `verdict.problems` stays a list with one string per distinct error, and the `N collectors failed (K distinct errors)` line is added where the text is rendered. `ErrorContext.collection_errors` is removed: its producer greps a string pytest never emits.

**Only exit code 5 means "No Tests Found".** A serial run where every collector fails now reaches the report parser and is classified as ERROR.

**The digest is computed from `files` alone.** Header totals are always summed from `files`, never read from the JSON's `totals`. Narrowing is therefore just passing a filtered `{"files": ...}` to the same function, with no "narrowed or not" branch.

**A run's failure state is one small value.** `run_outcome(report, verdict)` returns a `RunOutcome` TypedDict (`failed_collectors`, `failed_tests`, `generic_warning`). The same value is passed to the digest, stored in the metadata, and summed across merged runs.

**New module `code_checker_pytest/coverage_store.py` owns all saved data:** freshness roots and hashes, save/load/clear, reuse, merge. Both callers (`checker_tools/pytest_tool.py` and `toolkit.py`) use the same two calls:

```
run = start_coverage_run(...)                      # hashes at run start
... check_code_with_pytest(...) ...
finished = finish_coverage_run(run, data, report, verdict)   # save, merge or clear
```

`pytest_tool.py` keeps the calls to `read_coverage_report` and `format_coverage_digest`, because `test_server_params.py` patches them there. In the toolkit, `finish_coverage_run` runs right after `check_code_with_pytest`, before all three early returns.

**Storage** is `.mcp-tools-py/coverage/` in the target project:

```
.gitignore                 "*"
last_run.json              compact JSON, replaced last with os.replace
run-<uuid>.coverage        one per merged selection, referenced from last_run.json
```

`last_run.json` is a plain dict:

```python
{
    "version": 1,
    "report": {...},           # the coverage JSON, re-dumped compact
    "hashes": {"src/a.py": "<sha256>"},   # POSIX relative path -> digest
    "roots": ["src", "tests"],  # freshness roots
    "sources": ["src"],        # resolved, normalized, sorted measured sources
    "fail_under": 0.0,         # or null
    "runs": [
        {
            "identity": "<json string>",
            "selection": "selection: ...",
            "data_file": "run-<uuid>.coverage",  # or null
            "failed_collectors": 0,
            "failed_tests": 0,
            "generic_warning": False,
        }
    ],
}
```

**One fallback for every merge problem.** A hash or source mismatch and a failed `combine`/`json` all become "save only the new run, and add a note saying the saved runs were discarded".

**No changes to architecture contracts.** `coverage_store.py` sits in `code_checker_pytest` and imports only its own package and `utils`, so `tach.toml` and `.importlinter` stay as they are.

## Choices the issue leaves open

| Topic | Choice |
|---|---|
| Merge timeout | The run's resolved pytest timeout. No new constant |
| Zero-coverage collapse | Never above the common prefix |
| `max_modules=0` | Keeps the `N further modules have gaps` line, since it is a count and not a ranking |
| Reuse reply | No extra "no tests ran" line; it has no pytest summary above it |
| Merged run's hashes and `fail_under` | Those of the new run |
| Merged selection line | Joined on one line with ` + `, identical lines deduped |
| Single-collector group | No node ID line, as in the issue's sample |
| Collectors without `longrepr` | Counted in the header, no group of their own; the ERROR tail fallback still applies when none has one |
| Package table | Rows with 0 statements are skipped, so an empty `__init__.py` adds no `(root)` row |
| Absolute `coverage_source` on reuse | Not converted; it matches nothing and is refused |
| Save failure in the toolkit | Logged, and appended to `raw` only when a digest exists |
| `coverage < 7.6` | Not probed, accepted. Reading the code found nothing merge-specific, and the digest degrades to file-level ranges at `coverage.py:215` as it does today |

## Files

**Created**

```
src/mcp_tools_py/code_checker_pytest/coverage_store.py
tests/_coverage_project.py
tests/test_code_checker_pytest/_coverage_report.py
tests/test_code_checker_pytest/test_collector_groups.py
tests/test_code_checker_pytest/test_coverage_package_table.py
tests/test_code_checker_pytest/test_coverage_zero_list.py
tests/test_code_checker_pytest/test_coverage_selection_identity.py
tests/test_code_checker_pytest/test_coverage_store.py
tests/test_code_checker_pytest/test_coverage_merge.py
tests/test_code_checker_pytest/test_integration_collection_errors.py
tests/test_pytest_tool_reuse.py
tests/test_pytest_tool_combine.py
tests/test_toolkit_saved_coverage.py
tests/test_subprocess_tracing.py
```

**Modified**

```
src/mcp_tools_py/code_checker_pytest/reporting.py
src/mcp_tools_py/code_checker_pytest/verdict.py
src/mcp_tools_py/code_checker_pytest/models.py
src/mcp_tools_py/code_checker_pytest/utils.py
src/mcp_tools_py/code_checker_pytest/runners.py
src/mcp_tools_py/code_checker_pytest/coverage.py
src/mcp_tools_py/checker_tools/__init__.py
src/mcp_tools_py/checker_tools/pytest_tool.py
src/mcp_tools_py/toolkit.py
src/mcp_tools_py/utils/project_config.py
pyproject.toml
README.md
docs/architecture/architecture.md
tests/test_code_checker_pytest/test_verdict.py
tests/test_code_checker_pytest/test_coverage.py
tests/test_code_checker/test_reporting.py
tests/test_checker_tools_formatting.py
tests/test_server_params.py
tests/test_pytest_tool_coverage.py
tests/test_project_config.py
tests/test_toolkit_test.py
tests/test_startup_time.py
```

## Steps

| Step | Commit | Issue part |
|---|---|---|
| 1 | Group failed collectors by cause on both paths | 1 |
| 2 | Drop the false exit-code line and `collection_errors` | 1 |
| 3 | Treat only exit code 5 as No Tests Found | 1 |
| 4 | Replace `tests_failed` with counts and warning lines; handle no-report runs | 2 |
| 5 | Compute totals from `files`; add the package table | 2 |
| 6 | Collapse the zero-coverage list; `max_modules` controls only the ranking | 2 |
| 7 | Add the coverage store: hashes, save, load, clear | 3 |
| 8 | Save or clear data from both callers | 3 |
| 9 | Add `use_last_coverage_run` | 3 |
| 10 | Add selection identity and the merge command | 4 |
| 11 | Add `combine_with_previous` | 4 |
| 12 | Enable subprocess tracing in this repo | 5 |

## Every step ends with

Tests written first, then `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`, plus the step's own integration tests, `run_pylint_check`, `run_mypy_check` and `run_format_code`, all passing, then one commit. New saved-data tests go in new files, so allowlisted `test_server_params.py` and `test_code_checker/test_reporting.py` don't grow.
