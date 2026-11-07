# Step 2 — 600 s default timeout for check depths

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step
(`pr_info/steps/step_2.md`) only. Use TDD: write the tests first, then the
code. Run pylint, pytest (`extra_args=["-n", "auto"]`) and mypy until all
pass, run `run_format_code`, and make exactly one commit.

## WHERE
- `src/mcp_tools_py/toolkit_checks.py`: new constant, `_run_check`.
- `tests/test_toolkit_check.py`: new class `TestRunCheckTimeout`.

## WHAT
- `_LONG_CHECK_TIMEOUT = 600  # seconds; mypy and pylint at every check depth (mypy has no cache on a fresh checkout)`
- `_LONG_CHECK_TOOLS = frozenset({"mypy", "pylint"})`
- `_run_check(context, depth)`: after the availability loop, run each tool
  with `replace(context, check_timeout=_LONG_CHECK_TIMEOUT)` when it is in
  `_LONG_CHECK_TOOLS`, else with `context` unchanged
  (`dataclasses.replace` is already imported). The other `check@full` tools
  keep their existing default (`DEFAULT_CHECK_TIMEOUT`, 120 s). Mention it
  in the docstring: mypy and pylint default to 600 s;
  `[tool.mcp-tools-py]` `<tool>-timeout` and `check-timeout` still win.

## HOW
`ToolContext.resolve_timeout` → `get_check_timeout(project_dir, tool, explicit, self.check_timeout)`.
Its order is explicit → `<tool>-timeout` → `check-timeout` → cli value →
default. Setting `check_timeout` changes only the cli slot, so project
settings keep priority. This mirrors `_run_test`'s use of
`_LONG_TEST_TIMEOUT`.

## Tests (write first)
In `tests/test_toolkit_check.py`, monkeypatch
`mcp_tools_py.toolkit_checks.run_mypy_check` and `...get_pylint_results`
with fakes that record `kwargs["timeout_seconds"]` and return a clean
result (`MypyResult`/`PylintResult`, or whatever the existing tests in this
file and `test_toolkit_check_mypy.py` use). Use `_write_check_project(tmp_path, _CLEAN_SRC)`.
- `test_default_is_600_for_mypy_and_pylint`: parametrize depth over
  `quick`, `standard`, `full`. Every recorded mypy/pylint timeout is 600.
  For `full`, also `monkeypatch.setitem` the other `_CHECK_RUNNERS` entries
  with fakes that record `context.resolve_timeout(tool)` and return
  `ActionResult(status="ok", summary="")`, and patch
  `ToolContext.is_tool_available` to `True`.
- `test_full_other_checks_keep_default_timeout`: depth `full`, same fakes.
  vulture, lint-imports, tach, ruff, bandit and deptry each record
  `DEFAULT_CHECK_TIMEOUT` (import it, don't hard-code 120).
- `test_project_tool_timeout_wins`: `pyproject.toml` has
  `[tool.mcp-tools-py]\npylint-timeout = 45\n`, depth `standard`. pylint
  records 45 and mypy records 600.
- `test_project_check_timeout_wins`: `check-timeout = 30`. Both record 30.

## DATA
No signature changes. `_run_check` still returns the merged `ActionResult`.
