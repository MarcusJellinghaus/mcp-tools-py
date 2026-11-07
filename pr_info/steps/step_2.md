# Step 2: Runner and replies accept `None`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, then implement this step only. Write the tests first, then the code. Run pylint, pytest (`extra_args=["-n", "auto", "-m", "not integration"]`) and mypy until they pass, format the code, and make exactly one commit. Don't change any default value: that's step 3.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/runners.py`: `run_tests`, `check_code_with_pytest`
- `src/mcp_tools_py/code_checker_pytest/coverage_store.py`: `start_coverage_run`, `freshness_roots`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`: `run_pytest_check`
- `src/mcp_tools_py/toolkit.py`: `_run_test`, new `_with_note`
- Tests: `tests/test_code_checker_pytest/test_test_paths_runner.py` (new), `tests/test_code_checker_pytest/test_coverage_store.py`, `tests/test_server_params.py`, `tests/test_toolkit_test.py`

## WHAT

```python
# runners.py: only these two annotations change
def run_tests(project_dir: str, test_folder: Optional[str], python_executable: str, ...) -> PytestReport: ...
def check_code_with_pytest(project_dir: str, python_executable: str, test_folder: Optional[str] = "tests", ...) -> Dict[str, Any]: ...

# coverage_store.py: only these two annotations change
def start_coverage_run(project_dir: str, temp_dir: str, test_folder: str | None, ...) -> CoverageRun: ...
def freshness_roots(project_dir: str, coverage_source: list[str] | None, test_folder: str | None) -> list[str]: ...

# toolkit.py
def _with_note(result: ActionResult, note: str | None) -> ActionResult: ...
```

## HOW

- **`runners.py`:** import `resolve_test_paths` from `mcp_tools_py.utils.project_config`. Update the `test_folder` docstrings to say `None` means resolve from `testpaths`.
- **`pytest_tool.py`:** read `test_results.get("test_paths_note")` and prepend it with the sanitizer notes. Use `.get`, because many tests hand-build results without the key.
- **`toolkit.py`** (as of `origin/main`): in `_run_test`, `context.test_folder` reaches `start_coverage_run` at `:253` and `check_code_with_pytest` at `:267`, and both pass `None` through unchanged. After `check_code_with_pytest`, read `result.get("test_paths_note")` and wrap the four returns after it in `_with_note`: "skipped" (`No Tests Found`), "error" with `format_error_text`, "error" with `failed_summary` (FAILED with no findings), and the final `action_result`. The early returns before the call (pytest unavailable, `resolve_coverage_source` error) have no note. Don't move the existing logic.

## ALGORITHM

`run_tests`: replace the single `command.append(...)` in the block that adds the default folder. Since #279 that block comes before `extra_args`; keep it there, because `test_run_tests_default_test_folder_before_extra_args` pins that order:

```python
if not skip_default_test_folder:
    paths, _ = resolve_test_paths(project_dir, test_folder)
    command.extend(os.path.join(project_dir, path) for path in paths)
```

`check_code_with_pytest`: resolve inside the existing `try`, so invalid TOML becomes an ERROR verdict through the existing `except`:

```python
note = None
try:
    if not skip_default_test_folder:
        _, note = resolve_test_paths(project_dir, test_folder)
    test_results = run_tests(...)  # test_folder passed through unchanged
    ...
    return {..., "test_paths_note": note}
except Exception as e:
    ...
    return {"verdict": RunVerdict(RunStatus.ERROR, [str(e)], 0), "test_paths_note": note}
```

`freshness_roots`: replace `candidates.append(test_folder)`. It needs its own `try`: `test_coverage_store.py:103` pins that an explicit folder survives invalid TOML, and `:76` pins the root order, so it must stay after `get_test_directories`.

```python
try:
    candidates += resolve_test_paths(project_dir, test_folder)[0]
except ValueError:
    pass
```

`_with_note`:

```python
if note:
    result.summary = f"{note}\n\n{result.summary}"
return result
```

## DATA

The result dict of `check_code_with_pytest` gains `test_paths_note: str | None` on both returns. Existing keys are unchanged.

## Tests

**`test_test_paths_runner.py`** (patch `execute_command` as `test_run_tests_default_test_folder_appended` in `tests/test_code_checker/test_runners.py` does):

- `run_tests` with `test_folder=None` and `testpaths = ["tests", "integration"]`: both joined paths are in the command.
- `run_tests` with `test_folder=None` and `skip_default_test_folder=True`: neither path is in the command.
- `check_code_with_pytest` with `test_folder=None`, `testpaths = ["nope"]` and `run_tests` patched:
  - On success, `test_paths_note` names `nope`.
  - When `run_tests` raises, the verdict is ERROR and `test_paths_note` is still there.
- With `skip_default_test_folder=True` and `testpaths = ["nope"]`, `test_paths_note` is `None`.
- With `test_folder=None` and invalid TOML, the verdict is ERROR and names `Invalid pyproject.toml`.

**`test_coverage_store.py`, class `TestFreshnessRoots`,** with `test_folder=None`:

- `testpaths = []` and `tests/` present: `tests` is a root.
- `testpaths = ["nope"]` and `tests/` present: `tests` is a root.
- `testpaths = ["pkgs/*/tests"]` and `pkgs/a/tests` present: the matched folder is a root.
- Invalid TOML: doesn't raise.

**`test_server_params.py`:** with `check_code_with_pytest` patched to return `make_pytest_results(test_paths_note="NOTE", ...)`, the reply of `run_pytest_check` starts with `NOTE`.

**`test_toolkit_test.py`:** with `check_code_with_pytest` patched to return a result with `test_paths_note="NOTE"`, assert the summary starts with `NOTE` on each of the four returns. Reuse the helpers already in that file: `_run_with` for the patch, `_passed_results` for the final return, `_error_results` for "skipped" and "error", and `_failed_results` with `_collector`/`_report` for FAILED with no findings. Add the cases as a new class next to `TestRunTestVerdictMapping`.
