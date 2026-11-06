# Step 6: Real-mypy integration tests

**Commit message:** `test(mypy): cover found-twice, import crash and plugin crash with real mypy`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, `pr_info/steps/step_6.md`. Steps 1 to 5 are already committed. Add the tests below. Run the checks listed in the summary, fix what they report, then make exactly one commit.

## WHERE

`tests/test_code_checker_mypy/test_integration.py`. Follow the file's style: real `run_mypy_check` with `python_executable=sys.executable`. Use `tmp_path`.

Mark nothing as `integration`: the existing tests in this file have no marker and need only the local mypy.

## WHAT

```python
def test_mypy_found_twice_reports_early_stop(tmp_path: Path) -> None: ...
def test_mypy_crash_at_import_is_an_error(tmp_path: Path) -> None: ...
def test_mypy_plugin_crash_after_reveal_type_is_an_error(tmp_path: Path) -> None: ...
def test_toolkit_plugin_crash_after_reveal_type_is_not_ok(tmp_path: Path) -> None: ...
```

## HOW

Tests only, with no production code change. Share the plugin project between the two plugin tests through a small `_write_plugin_crash_project(project_dir)` helper.

If a fixture below does not give the rc stated here, a production fix is out of scope for this step: write one line to `pr_info/.blocked.txt` and stop.

## ALGORITHM: fixtures

These were all probed against mypy 2.4.1.

**Found twice:** targets `["src", "tests"]`. Expected rc 2, one message.
```
pyproject.toml         [tool.mypy]\nmypy_path = "src"\n
src/pkg/__init__.py    (empty)
src/pkg/mod.py         (empty)
src/pkg/cli.py         import src.pkg\nimport pkg.mod\n
tests/__init__.py      (empty)
tests/test_cli.py      import src.pkg.cli\nimport pkg.cli\n
```

**Crash at import:** targets `["mod.py"]`. Expected rc 1, traceback on stderr.
```
typing_extensions.py   raise RuntimeError('shadowed')\n
mod.py                 x: int = 1\n
```

**Plugin crash:** targets `["src"]`. Expected rc 2, one note on stdout, `INTERNAL ERROR` on stderr.
```
pyproject.toml         [tool.mypy]\nplugins = ["crash_plugin.py"]\n
crash_plugin.py        class P(Plugin) whose get_function_hook raises RuntimeError when
                       fullname.endswith(".boom"), else returns None; def plugin(version): return P
src/a_first.py         reveal_type(1)\n
src/z_last.py          from a_first import *\ndef boom() -> None: ...\nboom()\n
```

## DATA: assertions

**Found twice**
- `run_mypy_check`: `return_code == 2`, `error is None`, one message with `line == -1` and `code is None`, non-empty `hint`.
- `get_mypy_prompt`:
  - starts with the early-stop line
  - contains `Source file found twice` and `Common resolutions include`
  - does not contain `:-1:-1` or `To fix these issues:`
- `get_mypy_prompt(..., max_issues=0)`: still contains `Source file found twice`.

**Crash at import**
- `return_code == 1`, `messages == []`.
- `error` starts with `mypy exited with code 1:` and contains `RuntimeError: shadowed`.
- `get_mypy_prompt` starts with `MYPY_FAILURE_PREFIX`.

**Plugin crash, runner**
- `return_code == 2`, `messages == []`.
- `error` starts with `mypy exited with code 2:` and contains `INTERNAL ERROR`.

**Plugin crash, toolkit**
- `PythonToolkit().run(ActionRequest(action="check", depth="quick", project_dir=tmp_path, params={}))`.
- `status == "error"`, `summary` has no newline, `INTERNAL ERROR` in `raw`.

Do not assert the mypy version, a hint on every finding, or exact traceback text. Do not include a stub import in the found-twice layout, so the test does not depend on what is installed in the venv.
