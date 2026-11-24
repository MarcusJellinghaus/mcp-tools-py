# Step 7 — Wire sizing into `check_code_with_pytest`

## LLM prompt
Read `pr_info/steps/summary.md`, then implement **this step only** (`pr_info/steps/step_7.md`).
First write `tests/test_code_checker_pytest/test_workers_runner.py` and `tests/test_code_checker_pytest/test_integration_workers.py`, then change `check_code_with_pytest` in `src/mcp_tools_py/code_checker_pytest/runners.py`.
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`), then pytest on `tests/test_code_checker_pytest/test_integration_workers.py`, then mypy; all must pass. Make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/runners.py`
- Create `tests/test_code_checker_pytest/test_workers_runner.py`
- Create `tests/test_code_checker_pytest/test_integration_workers.py`

## WHAT
```python
def check_code_with_pytest(
    project_dir: str,
    python_executable: str,
    ...,                                  # unchanged parameters
    skip_default_test_folder: bool = False,
    effective: EffectiveConfig | None = None,   # new, last
) -> dict[str, Any]:
```
New keys on **every** return dict (success and the `except` return):
- `"workers_note": str | None`
- `"workers_serial": bool`

## HOW
- Import `EffectiveConfig`, `effective_config` from `pytest_config`, and `resolve_workers` from `workers`.
- Before the existing `try` (both are documented never to raise):
  ```python
  if effective is None:
      effective = effective_config(project_dir, markers, extra_args or [], env_vars)
  plan = resolve_workers(effective, env_vars)
  ```
- Pass `plan.env` to `run_tests` where `env_vars` is passed today. `run_tests` is unchanged.
- Add `"workers_note": plan.note, "workers_serial": plan.serial` to both return dicts.
- Docstring: document `effective` and the two new keys ("present on every return").
- `tests/test_code_checker/test_runners.py::test_check_code_with_pytest_with_custom_parameters` must still pass **unchanged**: no `-n` and no config, so `plan.env is env_vars`. Verify this.

## ALGORITHM
```
effective = effective or effective_config(...)
plan = resolve_workers(effective, env_vars)
try: run_tests(..., plan.env, ...) → result dict + workers keys
except: error dict + workers keys
```

## DATA
See the summary for `WorkersPlan` and the line formats.

## Tests (write first)
`test_workers_runner.py` (patch `mcp_tools_py.code_checker_pytest.runners.run_tests`):
- Config `pytest_workers = 4`, `extra_args=["-n", "auto"]` → `workers_note == "workers: 4 (config.toml)"`, `workers_serial is False`, and `run_tests` got an env with `PYTEST_XDIST_AUTO_NUM_WORKERS == "4"`.
- **No restart:** same call twice with `user_config` rewritten from `4` to `2` between the calls → notes `4` then `2`.
- `pytest_workers = 0` → `workers_serial is True`, note `workers: serial (config.toml)`.
- `run_tests` raising → the error dict still carries `workers_note` / `workers_serial`.
- A passed `effective` is used as given: patch `runners.effective_config` and assert it is not called.
- No `-n`, no config → note `None`, env passed through as the same object.

`test_integration_workers.py` (`@pytest.mark.integration`, `pytest.importorskip("xdist")`, modelled on `test_integration_xdist_collection.py`):
- A `tmp_path` project with one test asserting `"PYTEST_XDIST_WORKER" not in os.environ`.
- Run `check_code_with_pytest(str(tmp_path), python_executable=sys.executable, extra_args=["-n", "auto"], env_vars={"PYTEST_XDIST_AUTO_NUM_WORKERS": "0"}, timeout_seconds=120)` → PASSED, `workers_serial`, note `workers: serial (PYTEST_XDIST_AUTO_NUM_WORKERS)`. This proves that `=0` runs serially.
- Same with `user_config("[mcp_tools_py]\npytest_workers = 0\n")` and no `env_vars` → PASSED, note `workers: serial (config.toml)`.
- Control: `pytest_workers = 2` with a test asserting `"PYTEST_XDIST_WORKER" in os.environ` → PASSED.
