# Step 2 — `run_pytest_check` pre-run checks

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_2.md`).
> Step 1 (`ToolContext.is_distribution_available`) is already done.
> Implement only this step, test first. Then run `run_format_code`, pylint, mypy and
> pytest (`extra_args=["-n", "auto", "-m", "not integration"]`); all must pass.
> This step is exactly one commit.

## WHERE

- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `tests/test_tool_availability/test_handler_short_circuit.py`
- `tests/test_server_params.py` (class `TestPytestCoverage`)
- `tests/test_code_checker_pytest/test_output_budget.py` (fixture `run_pytest_check`)

## WHAT

No new functions. Inside `run_pytest_check`:

- Directly after `if not context.is_tool_available("pytest"): return …`, add the loop below.
- Delete the old block inside `try` / `if coverage:`
  (`info = get_environment_info(interpreter)` and the `pytest-cov` refusal).
- Remove the `from mcp_tools_py.utils.environment_info import get_environment_info` import.

## HOW

Order in `run_pytest_check` becomes: `use_last_coverage_run` path (unchanged, returns
earlier) → `combine_with_previous` check → pytest → pytest-json-report → pytest-cov
(only `coverage=True`) → `resolve_coverage_source` → ….

## ALGORITHM

```
required = ("pytest-json-report", *(("pytest-cov",) if coverage else ()))
for name in required:
    if not context.is_distribution_available(name):
        return context.unavailable_message(name)
```

## DATA

Return value on refusal: the standard `context.unavailable_message(name)` string,
e.g. `"pytest-json-report is not available in the configured Python environment (…)…"`.

## Tests (write first)

1. `test_handler_short_circuit.py` — new test next to `test_pytest_unavailable_returns_error`:
   - patch `_GET_ENVIRONMENT_INFO` with `make_environment_info(distributions={})`
     and `_PYTEST_RUNNER` (as `mock_check`);
   - call `tools["run_pytest_check"]()`;
   - assert `"pytest-json-report is not available" in result`,
     `"Restart the server" in result`, `mock_check.assert_not_called()`.
2. Patch-target move (these patches would raise `AttributeError` once the import is gone):
   - `tests/test_server_params.py`: every `patch(f"{_PYTEST_TOOL}.get_environment_info", …)`
     → `patch("mcp_tools_py.utils.tool_context.get_environment_info", …)` (add a module
     constant `_GET_ENVIRONMENT_INFO` next to `_PYTEST_TOOL`). In the fixture, use
     `distributions={"pytest-json-report": "1.5.0", "pytest-cov": "7.1.0"}`.
     `test_missing_pytest_cov_is_refused` keeps `make_environment_info()` (default has
     json-report, lacks pytest-cov → still refused for pytest-cov).
     `test_failed_probe_lets_the_run_proceed` keeps its broken probe (both checks fail open).
   - `tests/test_code_checker_pytest/test_output_budget.py` fixture: same target move and
     the same two-distribution dict.
3. Search `tests/` for any other `pytest_tool.get_environment_info` patch and move it the same way.
