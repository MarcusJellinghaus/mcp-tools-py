# Step 4 — `test@quick` excludes registered `*integration` markers

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step
(`pr_info/steps/step_4.md`) only. Use TDD: write the tests first, then the
code. Run pylint, pytest (`extra_args=["-n", "auto"]`) and mypy until all
pass, run `run_format_code`, and make exactly one commit.

## WHERE
- `src/mcp_tools_py/toolkit.py`: new `_registered_markers`, `_run_test`.
- `tests/test_toolkit_markers.py` (new).

## WHAT
```python
_MARKER_LINE = re.compile(r"^@pytest\.mark\.([^(:]+)", re.MULTILINE)

def _registered_markers(context: ToolContext) -> list[str] | str:
    """Names of the markers registered in the project, read via `pytest --markers`.

    Returns:
        The marker names, or an error message when the list can't be read:
        timeout, run failure, non-zero exit, or exit 0 with no marker lines
        (pytest's built-in markers always print, so no lines means the output
        wasn't understood).
    """
```
Import `execute_command` from `mcp_tools_py.utils.subprocess_runner` (the
shim; never `mcp_coder_utils`).

## ALGORITHM
```
result = execute_command([interpreter, "-m", "pytest", "--markers", "--color=no"],
                         cwd=str(project_dir), timeout_seconds=context.resolve_timeout("pytest"))
if result.timed_out or result.execution_error or result.return_code != 0:
    return "Could not read the project's pytest markers: <reason/stderr tail>"
names = [m.strip() for m in _MARKER_LINE.findall(result.stdout)]
return names or "Could not read the project's pytest markers: no marker lines in the output"
```
In `_run_test`, replace the hard-coded `"quick": ["not integration"]`:
```
if depth == "quick":
    names = _registered_markers(context)
    if isinstance(names, str): return ActionResult(status="error", summary=names)
    markers = [f"not {n}" for n in names if n.endswith("integration")] or None
```
Do this after the pytest availability check. `unattended` and the other
depths don't change. Add no `-o strict_markers=false` for `quick`. Update
the `_run_test` docstring: `quick` excludes every registered marker ending
in `integration`, and a failed marker read is `error`.

## Tests (write first)
New `tests/test_toolkit_markers.py`. For the unit cases, patch
`mcp_tools_py.toolkit.execute_command` with `make_command_result(...)`
from `tests.conftest`, and patch `mcp_tools_py.toolkit.check_code_with_pytest`
with passing results (copy the `_report` / `make_pytest_results` pattern
from `tests/test_toolkit_test.py`). Assert on `call_args.kwargs["markers"]`.
- `test_registered_integration_markers_are_excluded`: stdout has lines for
  `integration`, `git_integration: desc`, `slow: mentions @pytest.mark.llm_integration`
  and a built-in `@pytest.mark.skip(reason=None): ...`. markers ==
  `["not integration", "not git_integration"]`. The marker named only in a
  description is not included.
- `test_marker_with_arguments`: line `@pytest.mark.llm_integration(model): runs an LLM`
  → `["not llm_integration"]`.
- `test_none_registered_runs_unfiltered`: only built-in lines → markers is `None`.
- `test_nonzero_exit_is_error`: `return_code=4` → status `error`, and
  `check_code_with_pytest` is not called.
- `test_exit_zero_without_marker_lines_is_error`: `return_code=0`,
  stdout `"garbage"` → `error`, pytest not called.
- `test_timeout_is_error`: `timed_out=True` → `error`.
- Real run (no patching), `test_strict_marker_project_with_conftest_registration`:
  - `pyproject.toml` has `[tool.pytest.ini_options]\naddopts = "--strict-markers"\n`.
  - A top-level `conftest.py` registers `llm_integration` via
    `pytest_configure(config): config.addinivalue_line("markers", "llm_integration: real LLM")`.
  - `tests/test_mixed.py` has a passing `test_ok` and a failing test marked
    `@pytest.mark.llm_integration`.
  - `run(depth="quick")` → status `ok`.

  This covers a registration outside `pyproject.toml` and a real
  strict-marker run.

Check that the existing quick tests in `tests/test_toolkit_test.py` and
`tests/test_toolkit_saved_coverage.py` still pass. They now do a real
marker read in `tmp_path`, which is fine.

## DATA
- `_registered_markers` → `list[str]` (names, stripped) or `str` (error).
- `markers` passed to `check_code_with_pytest` at `quick`: `list[str]` of
  `"not <name>"`, or `None`.
