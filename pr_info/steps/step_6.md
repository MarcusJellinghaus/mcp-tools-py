# Step 6 — Toolkit `check` → `full` runs deptry

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_6.md`. Write the tests first, then the code. Use `_run_bandit` in `toolkit_checks.py` as the model. Run the checks listed in the summary and commit once.

## Precondition

`TestRunCheckFull` in `tests/test_toolkit_check.py` uses the real environment probe, so deptry must be importable in the project env. Check with `mcp__mcp-tools-py__get_library_source("deptry")`. If it is not found, write one line to `pr_info/.blocked.txt` (`deptry is not installed in the project env`) and stop.

## WHERE

- `src/mcp_tools_py/toolkit_checks.py`
- `src/mcp_tools_py/toolkit.py`
- `tests/test_toolkit.py`, `tests/test_toolkit_check.py`

## WHAT

```python
def _run_deptry(context: ToolContext, depth: str) -> ActionResult: ...
```

- `_CHECK_DEPTHS["full"]`: append `"deptry"` after `"bandit"`.
- `_CHECK_RUNNERS`: add `"deptry": _run_deptry`.
- `toolkit.py` `llm_permissions["check"]["full"]`: append `"mcp__mcp-tools-py__run_deptry_check"`.
- `check_instructions`: `"Run pylint, mypy and pytest via the MCP tools. At full depth, also run the other checkers, including deptry."`. Keep it one sentence pair; there is no test for its exact text.
- `verify()` stays unchanged.

## HOW

Imports in `toolkit_checks.py`: `run_deptry_check_impl` from `mcp_tools_py.code_checker_deptry.runners`, and `resolve_source_directories` from `utils.project_config`. Availability is already checked by `_run_check`.

## ALGORITHM

```
del depth
dirs = resolve_source_directories(project_dir, None); if str: return ActionResult(status="error", summary=dirs)
result = run_deptry_check_impl(str(context.environment.interpreter), project_dir, dirs, timeout_seconds=context.resolve_timeout("deptry"))
findings = [Finding(key=f"{m.file}|{m.code}|{m.module}", message=m.message, path=m.file, rule=m.code) for m in result.messages]
return _result_from_findings(result.error, findings, "deptry found no issues.", f"deptry found {len(findings)} issue(s).")
```

## DATA

`ActionResult` with status `ok`, `findings` or `error`.

## Tests (write first)

- `tests/test_toolkit.py`: add `"mcp__mcp-tools-py__run_deptry_check"` at the end of `_EXPECTED_PERMISSIONS["check"]["full"]`.
- `tests/test_toolkit_check.py`:
  - `_patch_full_depth_clean` also patches `mcp_tools_py.toolkit_checks.run_deptry_check_impl` to return `DeptryResult(return_code=0, messages=[])`
  - deptry findings → `status == "findings"`, and two DEP002 entries on `pyproject.toml` with different modules give two distinct keys
  - a deptry error result → `status == "error"`
  - the targets passed exclude tests (assert the captured `target_directories`)
  - deptry unavailable (`is_tool_available` returns False for `"deptry"`) → `status == "error"` and nothing runs
  - deptry is not run at `standard` depth.
