# Step 5 — pytest `PATH` prepend: `venv_path` → `venv_bin`

Implements **Decision 10**. See [summary.md](./summary.md) §7.

The third consumer of `venv_path`, and the easiest to miss. Independent of Steps 6
and 7; depends on Steps 1-4 only for `_resolved_python` being validated.

## WHERE

| File | Line(s) | Change |
|---|---|---|
| `src/mcp_tools_py/code_checker_pytest/runners.py` | `:89` | `run_tests` parameter rename |
| | `:104` | `run_tests` docstring |
| | `:132` | structured log field `"venv_path": venv_path` |
| | `:151` | explanatory comment |
| | `:202-208` | `PATH` prepend; the local `venv_bin` is subsumed |
| | `:477` | `check_code_with_pytest` parameter rename |
| | `:492` | `check_code_with_pytest` docstring |
| | `:516-528` | **positional** pass-through to `run_tests` |
| `src/mcp_tools_py/checker_tools/pytest_tool.py` | `:106` | call site |
| `tests/test_server_params.py` | `:82` | `assert_called_once_with(..., venv_path=None, ...)` |
| `tests/test_code_checker/test_runners.py` | `:229` | positional argument comment |

**Three** signature-adjacent sites, not two: `check_code_with_pytest` passes the
value to `run_tests` positionally.

## WHAT

```python
def run_tests(
    ...,
    venv_bin: Optional[str] = None,   # was venv_path
    ...
) -> PytestReport:
    """...
    venv_bin: Optional bin/Scripts directory to prepend to PATH. This is the
        directory the interpreter lives in, not a virtual environment root.
    """

def check_code_with_pytest(
    ...,
    venv_bin: Optional[str] = None,   # was venv_path
    ...
) -> Dict[str, Any]:
```

Call site in `pytest_tool.py`:

```python
venv_bin=str(Path(server._resolved_python).parent),   # was venv_path=server.venv_path
```

## HOW

- The parameter's **meaning** changes from venv root to bin directory. The function
  currently appends `Scripts`/`bin` itself (`:203-206`), so the resolved script
  directory cannot simply be passed in under the old name — the join moves to the
  call site and the branch inside disappears.
- `runners.py:204/206` already binds a local named `venv_bin`. The new parameter
  **subsumes** that local rather than conflicting with it; delete the local and the
  `os.name` branch around it.
- `Path(_resolved_python).parent`, **not** `parent.parent` — for a non-venv
  interpreter (`C:\Python311\python.exe`) `parent.parent` is `C:\`.
- Do **not** remove the prepend.
- `pytest_tool.py` has no `pathlib` import today; add `from pathlib import Path`.
- Keep `Optional[str] = None` and the `if venv_bin:` guard: other callers, including
  tests, still omit it.

## ALGORITHM

`runners.py:201-208` becomes:

```
# Prepend the interpreter's bin/Scripts directory so tests find its console scripts
if venv_bin:
    env["PATH"] = f"{venv_bin}{os.pathsep}{os.environ.get('PATH', '')}"
```

## DATA

`venv_bin: Optional[str]` — an absolute directory path, or `None` for no prepend.
No return-value changes anywhere.

## TESTS (write first)

1. **New** in `tests/test_code_checker_pytest/test_runners.py` (or alongside the
   existing `run_tests` tests): passing `venv_bin="/some/bin"` puts exactly
   `/some/bin` at the front of the subprocess `PATH` — no `Scripts` or `bin`
   appended. This is the regression guard for the meaning change.
2. **New** in `tests/test_tool_availability.py::TestToolHandlerShortCircuit`:
   `run_pytest_check` calls `check_code_with_pytest` with
   `venv_bin == os.path.dirname(server._resolved_python)`, and does so even when
   `server.venv_path` is `None`.
3. **Fix** `tests/test_server_params.py:74-85` — `assert_called_once_with` is
   strict; `venv_path=None` becomes `venv_bin=<the resolved interpreter's parent>`.
4. **Fix** `tests/test_code_checker/test_runners.py:221-233` — the argument is
   positional (position 8); update the `# venv_path` comment to `# venv_bin`. If
   #227 landed first it edits line 231 in the same list; re-read before editing.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_5.md`. Steps 1-4 are done.
>
> Implement Step 5 only: rename the `venv_path` parameter to `venv_bin` in both
> `run_tests` and `check_code_with_pytest` in
> `src/mcp_tools_py/code_checker_pytest/runners.py`, and change its meaning from
> "virtual environment root" to "bin/Scripts directory". The `Scripts`/`bin` join
> currently done inside `run_tests` moves to the call site in
> `checker_tools/pytest_tool.py:106`, which passes
> `str(Path(server._resolved_python).parent)` — not `parent.parent`, which for
> `C:\Python311\python.exe` would give `C:\`. Do not remove the `PATH` prepend.
>
> Watch for three things: `check_code_with_pytest` passes the value to `run_tests`
> **positionally**, so the rename lands in three places rather than two;
> `runners.py:204/206` already binds a local named `venv_bin` which the new
> parameter subsumes (delete the local and its `os.name` branch); and the
> structured log field at `:132` plus the explanatory comment at `:151` both name
> the old parameter.
>
> Write the tests first. `tests/test_server_params.py:82` uses
> `assert_called_once_with`, which is strict, and
> `tests/test_code_checker/test_runners.py:229` passes the argument positionally.
> Add a regression test that `venv_bin` is prepended to PATH verbatim, with no
> `Scripts`/`bin` appended.
>
> Then run, in order: `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`,
> `run_mypy_check`. All must pass. Commit as one commit.
