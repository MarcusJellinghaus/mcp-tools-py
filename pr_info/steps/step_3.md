# Step 3 — Toolkit `_run_test` pre-run checks

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_3.md`).
> Step 1 (`ToolContext.is_distribution_available`) is already done.
> Implement only this step, test first. Then run `run_format_code`, pylint, mypy and
> pytest (`extra_args=["-n", "auto", "-m", "not integration"]`); all must pass.
> This step is exactly one commit.

## WHERE

- `src/mcp_tools_py/toolkit.py` — `_run_test`
- `tests/test_toolkit_test.py`

## WHAT

No new functions. In `_run_test`, directly after the existing
`if not context.is_tool_available("pytest"): return ActionResult(...)` and before
`if depth != "quick": context = replace(...)`, add the loop below. Update the
`Returns:` docstring: "error" if pytest, pytest-json-report or (at `full`) pytest-cov
is unavailable, ….

## HOW

The placement puts both checks before `_registered_markers` (`pytest --markers`), before
`tempfile.mkdtemp`, before `start_coverage_run` and before `check_code_with_pytest`.
Saved coverage data is only cleared in `finish_coverage_run`, which a refusal never reaches.

## ALGORITHM

```
required = ["pytest-json-report", *(["pytest-cov"] if depth == "full" else [])]
for name in required:
    if not context.is_distribution_available(name):
        return ActionResult(status="error", summary=context.unavailable_message(name))
```

## DATA

`ActionResult(status="error", summary=<standard unavailable_message>)`.

## Tests (write first) — new class `TestRunTestPreflight` in `tests/test_toolkit_test.py`

Patch `"mcp_tools_py.utils.tool_context.get_environment_info"` in each test.

1. `quick` with `make_environment_info(distributions={})`, also patching
   `mcp_tools_py.toolkit.execute_command` and `mcp_tools_py.toolkit.check_code_with_pytest`:
   status `"error"`, `"pytest-json-report is not available" in summary`, both mocks not called.
2. `full` with `make_environment_info()` (json-report present, pytest-cov missing), also
   patching `mcp_tools_py.toolkit.check_code_with_pytest` and
   `mcp_tools_py.toolkit.finish_coverage_run`: status `"error"`,
   `"pytest-cov is not available" in summary`, both mocks not called (so saved data is
   never cleared).
3. `full` with a failed probe
   (`EnvironmentInfo(version="", sys_path=(), distributions={}, importable={}, error="boom")`),
   following `test_full_uses_long_timeout_for_pytest_and_coverage_run` (its
   `pytest.importorskip("pytest_cov")`, `_write_coverage_project(tmp_path)`, and patches
   of `mcp_tools_py.toolkit.check_code_with_pytest` returning `_passed_results()` and
   `mcp_tools_py.toolkit.finish_coverage_run` returning `None`): both checks fail open,
   so `check_code_with_pytest` is called once.

If adding the class would push `tests/test_toolkit_test.py` over 750 lines, put it in a new
file `tests/test_toolkit_test_preflight.py` instead.
If `src/mcp_tools_py/toolkit.py` exceeds 750 lines after this step, write one line to
`pr_info/.blocked.txt` and stop.
