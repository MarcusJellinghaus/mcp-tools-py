# Step 5 — Remove the auto-install; fix the timeout worst-case doc row

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_5.md`).
> Implement only this step, test first. Then run `run_format_code`, pylint, mypy and
> pytest (`extra_args=["-n", "auto", "-m", "not integration"]`); all must pass.
> This step is exactly one commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/runners.py` — `run_tests`
- `tests/test_code_checker/test_runners.py`
- `docs/pyproject-configuration.md`

## WHAT

- In `run_tests`, delete the whole block from `# Check if plugin is missing` through the
  `except Exception as install_error: … raise` (the `pip install pytest-json-report`
  call, its retry and both of its raises). Everything after it
  (`# Check specifically for 'no tests found' case` …) stays unchanged.
- Docstring `Raises:`: `RuntimeError: For pytest internal errors, plugin errors, or missing pytest.`
  (only the "or failure to install pytest-json-report" clause goes).

## Tests (write first)

1. Delete `test_run_tests_surfaces_pytest_output_on_install_and_retry_failures`
   (the parametrized function with `install_fail` / `retry_timeout`).
2. Add `test_run_tests_never_installs_packages` (patch
   `mcp_tools_py.code_checker_pytest.runners.execute_command`):
   - mock result: `return_code=1`, `stdout=""`,
     `stderr="No module named 'pytest_json_report'"`, `execution_error=None`, `timed_out=False`;
   - patch `runners.os.path.isfile` → `False`;
   - `pytest.raises(RuntimeError)` around `run_tests("/test/project", "tests", python_executable=sys.executable)`;
   - assert `mock_execute.call_count == 1` and no call's command contains `"pip"`.

## Docs — `docs/pyproject-configuration.md`

Replace the `run_pytest_check` row (currently "2 × `pytest-timeout` + 60s, when the
pytest-json-report plugin is missing and the run is retried") with:

```
| `run_pytest_check` | 3 × `pytest-timeout` + up to 2 × the 30 s probe timeout. pytest itself uses one; the other two are the coverage merge's `coverage combine --keep` and `coverage json`, which run only with `combine_with_previous=True`, saved earlier runs that each have a data file, and no mismatch discarding them (never from the toolkit). A plain coverage run writes its JSON through pytest-cov, so only pytest uses `pytest-timeout`. The probes are the environment probe on the first call and the `fail_under` read of each coverage run |
```
