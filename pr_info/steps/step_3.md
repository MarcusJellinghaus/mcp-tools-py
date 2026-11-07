# Step 3 — Project environment from `VIRTUAL_ENV`

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step
(`pr_info/steps/step_3.md`) only. Use TDD: write the tests first, then the
code. Run pylint, pytest (`extra_args=["-n", "auto"]`) and mypy until all
pass, run `run_format_code`, and make exactly one commit.

## WHERE
- `src/mcp_tools_py/toolkit.py`: `_build_context`, `PythonToolkit.run`,
  `PythonToolkit.verify`.
- `docs/architecture/architecture.md`: "Name Resolution" section.
- `tests/test_toolkit_environment.py` (new).
- `tests/test_toolkit_verify.py`.
- `tests/conftest.py`: autouse fixture clearing `VIRTUAL_ENV`.

## WHAT
```python
def _build_context(project_dir: Path) -> ToolContext:
    """... resolves VIRTUAL_ENV when set, else sys.executable ...

    Raises:
        FileNotFoundError: VIRTUAL_ENV is set but has no interpreter; the
            message names VIRTUAL_ENV.
    """
```
- `run`: wrap `_build_context(...)`. On `FileNotFoundError as exc` →
  `ActionResult(status="error", summary=str(exc))`.
- `verify`: same wrap (after the undeclared-action check). On error →
  `[VerifyItem(name="environment", status="error", message=str(exc))]`.
- Update the docstrings of `run` and `verify`, and the module-level
  `_build_context` docstring, which currently says "no venv_path override".

## ALGORITHM
```
venv = os.environ.get("VIRTUAL_ENV")          # "" counts as unset
if not venv: return ToolContext(project_dir, PythonEnvironment.resolve())
try: env = PythonEnvironment.resolve(venv_path=venv)
except FileNotFoundError as exc:
    raise FileNotFoundError(f"VIRTUAL_ENV is set to {venv}, but it has no Python interpreter. "
                            "Activate the project's environment or unset VIRTUAL_ENV.") from exc
return ToolContext(project_dir=project_dir, environment=env)
```
`tool_environment` keeps its default (`sys.executable`). Don't change
`PythonEnvironment` or `ToolContext`. A project env without a needed tool
already returns `error` through `is_tool_available`.

## Docs
Replace the quoted rule in "Name Resolution" so it still says names resolve
through `ToolContext.environment`, and add: the one exception is
`PythonToolkit._build_context`, which builds that environment from
`VIRTUAL_ENV` when it's set (else `sys.executable`), because mcp-coder can
run from its own tool env. A `VIRTUAL_ENV` with no interpreter is an error,
never a fallback.

## Tests (write first)
In `tests/conftest.py`, add an autouse fixture that runs
`monkeypatch.delenv("VIRTUAL_ENV", raising=False)`, so the existing
real-run toolkit tests (`test_toolkit_test.py`, `test_toolkit_verify.py`,
`test_toolkit_check*.py`, `test_toolkit_saved_coverage.py`) and step 4's
strict-marker run never pick up a `VIRTUAL_ENV` inherited from the shell
or CI. Every new `VIRTUAL_ENV` test below sets (or deletes) the variable
explicitly with `monkeypatch`.

New `tests/test_toolkit_environment.py`. Use `monkeypatch` and patch
`mcp_tools_py.toolkit.check_code_with_pytest`, or call `_build_context`
directly where that's simpler:
- `test_unset_uses_sys_executable`: `delenv("VIRTUAL_ENV", raising=False)`.
  `_build_context(tmp_path).environment.interpreter == Path(sys.executable)`.
- `test_empty_is_treated_as_unset`: `setenv("VIRTUAL_ENV", "")`. Same as unset.
- `test_set_uses_its_interpreter`: build a fake venv in `tmp_path`
  (`Scripts/python.exe` when `mcp_tools_py.utils.python_environment._IS_WINDOWS`
  is true, else `bin/python`; read that flag, the one
  `PythonEnvironment.resolve` uses, rather than `os.name`/`sys.platform`;
  an empty file is enough for `resolve`) and set `VIRTUAL_ENV` to it. The context's
  interpreter is that file, and `tool_environment.interpreter == Path(sys.executable)`.
- `test_stale_run_is_error_naming_virtual_env`: `VIRTUAL_ENV` →
  `tmp_path / "missing"`. `PythonToolkit().run(ActionRequest(action="test", depth="standard", ...))`
  has status `error` and `"VIRTUAL_ENV"` in its summary, and
  `check_code_with_pytest` is never called.

In `tests/test_toolkit_verify.py`:
- `test_stale_virtual_env_is_single_environment_error`: stale
  `VIRTUAL_ENV`. `verify(tmp_path)` returns exactly one item, named
  `environment`, with status `error` and `"VIRTUAL_ENV"` in its message.

## DATA
- `run` → `ActionResult(status="error", summary=<message naming VIRTUAL_ENV>)`.
- `verify` → `[VerifyItem(name="environment", status="error", message=...)]`.
