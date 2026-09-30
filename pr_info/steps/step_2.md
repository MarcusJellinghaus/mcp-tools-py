# Step 2 — Ruff command overrides and flag pre-check

## LLM prompt

Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_2.md`.
Write the tests first, then the implementation. Run pylint, pytest
(`-n auto`, including the new integration test) and mypy; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_ruff/runners.py`
- `src/mcp_tools_py/checker_tools/ruff_check_tool.py` (docstring only)
- `tests/test_code_checker_ruff/test_runners.py`
- `tests/test_code_checker_ruff/test_integration.py` (new)

## WHAT

```python
_STATISTICS_ERROR = (
    "--statistics changes ruff's output format and is not supported.\n"
    "Use the built-in rule counts in the summary instead."
)
_FIX_IN_CHECK_ERROR = (
    "{flag} modifies files and is not supported by run_ruff_check. "
    "Use run_ruff_fix instead."
)

def _rejected_flag(extra_args: list[str] | None, flags: tuple[str, ...]) -> str | None:
    """First token in extra_args that exactly equals one of flags, else None."""

def _build_ruff_command(...)  # signature unchanged; trailing overrides added
```

## HOW

- `run_ruff_check_impl`: after the `project_dir` check, call
  `_rejected_flag(extra_args, ("--statistics", "--fix", "--fix-only"))`; return
  `_STATISTICS_ERROR` or `_FIX_IN_CHECK_ERROR.format(flag=...)` without calling
  `execute_command`.
- `run_ruff_fix_impl`: same, with `("--statistics",)` only. `--fix`,
  `--unsafe-fixes` etc. stay accepted.
- `ruff_check_tool.py` docstring, `extra_args` line: add
  "`--fix`, `--fix-only` and `--statistics` are rejected."

## ALGORITHM

```
_build_ruff_command(...):
    cmd = [ruff, "check"] + (["--fix"] if fix else []) + ["--output-format", fmt]
    add --select if select
    add extra_args
    cmd += ["--no-fix-only"] if fix else ["--no-fix", "--no-fix-only"]
    cmd += target_directories
```

## DATA

- `_build_ruff_command(ruff, ["src"])` →
  `[ruff, "check", "--output-format", "json", "--no-fix", "--no-fix-only", "src"]`
- Rejected flag → the runner returns the error string; ruff is not run.

## Tests (write first)

Unit (`test_runners.py`):
- Update `TestBuildRuffCommand.test_basic` to the exact list above.
- `test_overrides_after_extra_args` — with `extra_args=["--fix"]`, `fix=False`:
  command ends `["--fix", "--no-fix", "--no-fix-only", "src"]`.
- `test_fix_appends_no_fix_only` — `fix=True`: ends `["--no-fix-only", "src"]`,
  and `"--no-fix"` not in cmd.
- `TestRunRuffCheckImpl`: parametrize over `--statistics`, `--fix`, `--fix-only`;
  assert the error text and `mock_exec.assert_not_called()`.
  `--statistics` returns exactly `_STATISTICS_ERROR`; fix flags mention `run_ruff_fix`.
- `TestRunRuffFixImpl`: `--statistics` rejected, ruff not run;
  `extra_args=["--unsafe-fixes"]` still runs ruff.

Integration (`test_integration.py`, `@pytest.mark.integration`):
- Ruff binary: `PythonEnvironment.resolve().binary("ruff")`; `pytest.skip` if None.
- Fixture project in `tmp_path`: `pyproject.toml` with `[tool.ruff]` + the
  parametrized line, `src/a.py` = `"import os\nl = 1\n"` (F401 fixable,
  E741 unfixable). Use `select=["F401", "E741"]`.
- Parametrize `config` over `"fix = true"` and `"fix-only = true"`:
  - `run_ruff_check_impl` → file content unchanged.
  - `run_ruff_fix_impl` → result contains `"a.py"` (fixed file) and `"E741"`
    (remaining issue); `import os` removed from the file.
