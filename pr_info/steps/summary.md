# Summary — #146: detect a missing pytest-json-report up front; remove the dead auto-install

## Goal

`run_pytest_check` and the toolkit's `test` action need `pytest-json-report` in the
project environment (`--python-executable`). Today a missing plugin surfaces only as a
pytest usage error, and a dead auto-install branch in `run_tests` would `pip install`
into the user's venv if it ever matched. This change:

- refuses a run up front with the standard `unavailable_message` when
  `pytest-json-report` (or, for coverage runs, `pytest-cov`) is missing — nothing is
  ever installed;
- removes the auto-install branch;
- adds `pytest-json-report` and `pytest-cov` rows to `PythonToolkit.verify("test")` /
  `verify(None)`;
- adds one `Command: …` line to every pytest ERROR reply caused by an exception caught
  in `run_tests`' inner handler;
- updates README and docs.

## Architectural / design changes

1. **One distribution check, one probe binding** (`utils/tool_context.py`).
   - New module function `distribution_available(info, name) -> bool`: exact match of
     `name` in `info.distributions` (keys are lowercased only); fails open (`True`)
     when `info.error` is set.
   - New method `ToolContext.is_distribution_available(name) -> bool`: calls the
     `get_environment_info` imported in `tool_context.py`, then the function above.
     That is the binding the conftest patch
     (`mcp_tools_py.utils.tool_context.get_environment_info`) covers.
   - Every distribution check (pytest-json-report and pytest-cov, in
     `run_pytest_check`, toolkit `_run_test` and `verify()`) goes through this method.
     `checker_tools/pytest_tool.py` no longer imports `get_environment_info`.
   - No logging in the method: `is_tool_available("pytest")` runs first in every caller
     and already logs a failed probe; the refusal message names the missing package.

2. **Pre-run checks are a short loop right after the pytest check**, in both callers:
   - `run_pytest_check`: `pytest-json-report`, plus `pytest-cov` when `coverage=True`
     (the old pytest-cov block inside `try` is replaced). The `use_last_coverage_run`
     path still returns earlier.
   - toolkit `_run_test`: `pytest-json-report`, plus `pytest-cov` at `full`. Placed
     before `_registered_markers` (`pytest --markers`), before the coverage temp dir
     and before `check_code_with_pytest`, so a refused `full` run never reaches
     `finish_coverage_run` → saved coverage data stays intact.

3. **`verify()` gets two rows** for `action in (None, "test")`:
   `pytest-json-report` (`ok` / `error` + standard message) and `pytest-cov`
   (`ok` / `warning` + short "only the `full` test depth needs it" note). Both are
   `ok` on probe failure (fail open).

4. **Auto-install removed** from `run_tests`; `RuntimeError` stays a documented raise.

5. **Command in error replies** (`code_checker_pytest/runners.py`):
   - `run_tests` builds a display command: the plain space-join of `command` without
     the temporary `--json-report-file=…` element.
   - The inner `except Exception as e` handler attaches it as an attribute via
     `setattr(e, _COMMAND_ATTR, …)` — type and message of the exception are unchanged.
   - `check_code_with_pytest` reads it with `getattr(e, _COMMAND_ATTR, None)` and
     appends `"Command: …"` as a **separate** `verdict.problems` entry after
     `str(e)` (so `problems[0]` and the toolkit's `"No Tests Found"` check keep working).
   - The timeout `TimeoutError` message no longer embeds the command inline.

## Files

### Modified — source
- `src/mcp_tools_py/utils/tool_context.py` — `distribution_available`, `ToolContext.is_distribution_available`
- `src/mcp_tools_py/checker_tools/pytest_tool.py` — pre-run check loop; drop `get_environment_info` import
- `src/mcp_tools_py/toolkit.py` — pre-run check loop in `_run_test`; `_distribution_items` + `verify()` rows
- `src/mcp_tools_py/code_checker_pytest/runners.py` — remove auto-install; attach/render command; timeout message

### Modified — tests
- `tests/conftest.py` — `make_environment_info` default `distributions`
- `tests/test_tool_context.py` — tests for `is_distribution_available`
- `tests/test_tool_availability/test_handler_short_circuit.py` — json-report refusal test
- `tests/test_server_params.py`, `tests/test_code_checker_pytest/test_output_budget.py` — patch target moves to `tool_context`
- `tests/test_toolkit_test.py` — toolkit refusal tests
- `tests/test_toolkit_verify.py` — new rows, mocked probe
- `tests/test_code_checker/test_runners.py` — remove install test; add no-install and `Command:` tests

### Modified — docs
- `README.md`
- `docs/architecture/architecture.md`
- `docs/pyproject-configuration.md`

### Created
- `pr_info/steps/summary.md`, `pr_info/steps/step_1.md` … `step_7.md` (this plan)

No new source modules or packages.

## Steps

1. Distribution check on `ToolContext` + conftest default
2. `run_pytest_check` pre-run checks
3. Toolkit `_run_test` pre-run checks
4. Toolkit `verify()` rows
5. Remove the auto-install; fix the timeout worst-case doc row
6. `Command:` line in pytest error replies
7. README and architecture docs

## Size constraints

CI runs `mcp-coder check file-size --max-lines 750`. `src/mcp_tools_py/toolkit.py` (690 lines)
and `tests/test_toolkit_test.py` (646 lines) are close; neither may be added to
`.large-files-allowlist`.
