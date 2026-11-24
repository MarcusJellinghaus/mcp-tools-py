# Step 4 — Toolkit `verify()` item `pytest_workers`

## LLM prompt
Read `pr_info/steps/summary.md`, then implement **this step only** (`pr_info/steps/step_4.md`).
First update and extend `tests/test_toolkit_verify.py`, then add the item in `PythonToolkit.verify()`.
Run `run_format_code`, pylint, pytest (`markers=["not integration"]`) and mypy; all must pass. Make one commit.

## WHERE
- `src/mcp_tools_py/toolkit.py` (`PythonToolkit.verify`)
- `tests/test_toolkit_verify.py`

## WHAT / HOW
- Import `pytest_workers_verify` from `mcp_tools_py.code_checker_pytest.workers`.
- In `verify()`, after `_build_context` (so the single "environment" error item stays alone), extend the test-related items:
  ```python
  distribution_items = (
      [*_distribution_items(context), VerifyItem("pytest_workers", *pytest_workers_verify())]
      if action in (None, "test")
      else []
  )
  ```
  `pytest_workers_verify()` returns `(status, message, hint)` in `VerifyItem` field order.
- Docstring of `verify()`: add `pytest_workers` to the `None` and `"test"` bullets.
- Keep the wiring to these few lines. `toolkit.py` is at 735 lines and must stay ≤ 750.

## DATA
`VerifyItem(name="pytest_workers", status="ok"|"warning", message=..., hint=None|str)`.

## Tests (write first)
- `test_healthy_environment_is_all_ok`: 14 → 15 items, add `"pytest_workers"` to the name set.
- `test_test_reports_pytest`: add `"pytest_workers"` to the name set.
- New, parametrized over `action` in `[None, "test"]`, using the `user_config` fixture from step 3:
  - no config → `ok`, message `auto (default)`
  - `pytest_workers = 4` → `ok`, message `4 (config.toml)`
  - `pytest_workers = "x"` → `warning`, hint names the valid values
  - invalid TOML → `warning`
- `"format"` / `"check"` actions don't include `pytest_workers`.
- The stale-`VIRTUAL_ENV` test still returns exactly one item.

## Precondition
If `toolkit.py` exceeds 750 lines after this step, move `_registered_markers` (and the `_MARKER_LINE` / `_MARKER_READ_FAILED` constants it uses) to `src/mcp_tools_py/toolkit_checks.py`. Import it back into `toolkit.py`, and change the patch targets `mcp_tools_py.toolkit.execute_command` in `tests/test_toolkit_markers.py` and `tests/test_toolkit_test.py` to `mcp_tools_py.toolkit_checks.execute_command`. If it is still over 750 after that, write one line to `pr_info/.blocked.txt` and stop.
