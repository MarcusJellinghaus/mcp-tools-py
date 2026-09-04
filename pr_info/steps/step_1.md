# Step 1 — `PythonEnvironment` value object

Collapses seven `Scripts`/`bin` branches into one and fixes the
`--python-executable`-only defect. No new behaviour beyond that fix.

**Acceptance criteria closed:** "One `Scripts`/`bin` branch exists in the codebase, not
seven", "With only `--python-executable` set, the console-script tools are found",
"`main.py` help text no longer contradicts the resolution target".

## WHERE

**Created**
- `src/mcp_tools_py/utils/python_environment.py`
- `tests/test_python_environment.py`

**Modified**
- `src/mcp_tools_py/server.py` — `_resolve_python_executable`, `_check_tool_availability`,
  the dead `self.venv_path` / `self.python_executable` attributes, and the flag docstrings
  at `:64-65` and `:282-283`
- `vulture_whitelist.py:26-27` — the `_.python_executable` / `_.venv_path` entries
- `src/mcp_tools_py/code_checker_pytest/runners.py` — `run_tests`, `check_code_with_pytest`
- `src/mcp_tools_py/checker_tools/pytest_tool.py:111` — call site
- `src/mcp_tools_py/main.py:66-85` — both help strings
- `tests/test_tool_availability.py` — patch targets move; three assertions invert;
  `TestResolvePythonExecutable`'s expected strings change form
- `tests/test_code_checker/test_runners.py:229` — positional comment
- `tests/test_server_params.py:83` — asserts `check_code_with_pytest(..., venv_path=None,
  ...)`; becomes `bin_dir=...` with a non-`None` value

## WHAT

```python
# src/mcp_tools_py/utils/python_environment.py

@dataclass(frozen=True)
class PythonEnvironment:
    """The Python environment that tools run in and that Python names resolve in."""

    interpreter: Path

    @classmethod
    def resolve(
        cls,
        python_executable: str | None = None,
        venv_path: str | None = None,
    ) -> "PythonEnvironment": ...

    @property
    def bin_dir(self) -> Path: ...

    def binary(self, name: str) -> Path | None: ...
```

`run_tests` and `check_code_with_pytest` (both public exports of
`code_checker_pytest`) replace `venv_path: Optional[str] = None` with
`bin_dir: Optional[Path] = None` **in the same position**.

## ALGORITHM

```
resolve(python_executable, venv_path):
    if venv_path:
        sub = "Scripts" if os.name == "nt" else "bin"      # the ONE directory branch
        exe = "python.exe" if os.name == "nt" else "python"
        p = Path(venv_path) / sub / exe
        if not os.path.exists(p): raise FileNotFoundError(f"Python executable not found in virtual environment: {p}")
        return cls(p)
    return cls(Path(python_executable or sys.executable))

bin_dir:            return self.interpreter.parent
binary(name):       p = bin_dir / (f"{name}.exe" if os.name == "nt" else name)
                    return p if os.path.exists(p) else None
```

Existence is checked through `os.path.exists`, not `Path.exists()`, so that `os.name` and
the existence check share one patchable module attribute
(`mcp_tools_py.utils.python_environment.os`) — the idiom the existing availability tests
already use. Patching `Path.exists` globally would be the alternative; this is narrower.

The `.exe` suffix in `binary()` is a filename branch, not a directory branch — it is the
only remaining one and it lives in one place. `bin_dir` never branches, which is what
fixes the `--python-executable`-only case.

## HOW — `server.py`

```python
self.environment = PythonEnvironment.resolve(python_executable, venv_path)
self._resolved_python = str(self.environment.interpreter)   # unchanged for callers
```

`_check_tool_availability` becomes a loop. Keep the five `_<tool>_binary` attributes for
now — the nine checker tool modules read them and step 6 rewrites those modules anyway:

```python
CONSOLE_SCRIPT_TOOLS = ("lint-imports", "vulture", "ruff", "bandit", "tach")

binaries: dict[str, Optional[str]] = {}
for name in CONSOLE_SCRIPT_TOOLS:
    path = self.environment.binary(name)
    availability[name] = path is not None
    binaries[name] = str(path) if path else None
    if path is None:
        logger.warning("%s not found in %s. Ensure --venv-path or --python-executable "
                       "points to an environment where %s is installed.",
                       name, self.environment.bin_dir, name)

# Declared explicitly, not via setattr — see below.
self._lint_imports_binary: Optional[str] = binaries["lint-imports"]
self._vulture_binary: Optional[str] = binaries["vulture"]
self._ruff_binary: Optional[str] = binaries["ruff"]
self._bandit_binary: Optional[str] = binaries["bandit"]
self._tach_binary: Optional[str] = binaries["tach"]
```

**The five attributes must stay declared.** A `setattr(self, f"_{name}_binary", ...)` loop
would be shorter, but mypy cannot see attributes assigned under a computed name, so every
reader in the nine tool modules becomes an `attr-defined` error —
`ruff_check_tool.py:41,66`, `ruff_fix_tool.py:42,66`, `bandit_tool.py:42,66`,
`lint_imports_tool.py:39,48`, `tach_tool.py:29,41`, `vulture_tool.py:40,64`. Passing mypy
is an exit criterion for this step. The five explicit lines keep today's annotations
(`Optional[str]`) and today's read sites working unchanged; step 6 deletes all five
attributes when the tool modules switch to `context.environment.binary(...)`.

Update the `_check_tool_availability` docstring — it currently lists "(lint-imports,
vulture, ruff, bandit)" and omits tach.

### Dead state to delete in the same commit

`self.venv_path` (`server.py:74`) and `self.python_executable` (`:73`) have exactly one
reader each today: `_resolve_python_executable` / `_check_tool_availability` for
`venv_path`, and `pytest_tool.py:111` for `server.venv_path`. This step removes all of
them — the two constructor **parameters** stay, but they are consumed by
`PythonEnvironment.resolve(...)` and stored nowhere else. Leaving the attributes behind
would leave the server carrying write-only state that no longer describes how anything
resolves. So:

- Delete `self.python_executable = python_executable` and `self.venv_path = venv_path`.
  `self.environment` replaces both.
- Delete the `_.python_executable` and `_.venv_path` entries at `vulture_whitelist.py:26-27`,
  then run `run_vulture_check`. If vulture reports either name from a **different** source
  — `main.py:192` reads them off the argparse `Namespace` — restore just that entry with a
  comment naming the real reason, rather than restoring both blindly.
- Update the `venv_path` / `python_executable` docstrings in `ToolServer.__init__`
  (`:64-65`) and `create_server` (`:282-283`). Both currently say the flags select an
  interpreter "for running tests"; they now also select the environment that library and
  symbol lookups resolve in. Use the same wording as the `main.py` help strings below.

`tests/test_checker_tools.py:20` sets `server.venv_path` on a `MagicMock`, which tolerates
a removed attribute silently; step 6's fixture migration drops it.

## HOW — `code_checker_pytest/runners.py`

Replace lines 201-208:

```python
if bin_dir:
    env["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
```

`pytest_tool.py:111` changes `venv_path=server.venv_path` to
`bin_dir=server.environment.bin_dir`, so PATH is now always prepended in server use
(the `--python-executable`-only fix). The `Optional` default preserves standalone
library use. Update the `venv_path` key in the `logger.info` extra at line 132 and the
stale comment at line 151.

## HOW — `main.py`

Both help strings say the flag should point at "the tool's own venv, not the project's
runtime venv", which is backwards. Replace with wording naming the **project**
environment, e.g.:

> Path to the Python interpreter of the project's environment. The checkers run in it and
> library/symbol lookups resolve against it, so it must be the environment holding the
> project's dependencies. Defaults to the current interpreter (sys.executable).

## DATA

`PythonEnvironment.binary()` returns `Path | None` — `None` means "not present".
`resolve()` raises `FileNotFoundError` when `venv_path` is set but its python is missing,
preserving today's fail-loud server construction (`server.py:109-112`).

## Tests (write first)

`tests/test_python_environment.py` — pure unit tests, no subprocess:

1. `venv_path` wins over `python_executable`; patch
   `mcp_tools_py.utils.python_environment.os.name` to `"nt"` and `"posix"` and assert the
   two layouts (use `tmp_path` and create the file so `exists()` is true).
2. `venv_path` set but missing python → `FileNotFoundError`.
3. Only `python_executable` set → used verbatim.
4. Neither set → `sys.executable`.
5. `bin_dir == interpreter.parent`, asserted by constructing `PythonEnvironment` directly
   (platform-independent).
6. `binary()` hit: create `tmp_path/ruff(.exe)` → returns that path.
7. `binary()` miss: returns `None`.
8. **The defect fix:** with only `python_executable` pointing at
   `tmp_path/Scripts/python.exe` (or `bin/python`) and `tmp_path/.../ruff(.exe)` present,
   `binary("ruff")` is not `None`.

`tests/test_tool_availability.py` churn:

- Patch targets `mcp_tools_py.server.os.name` / `.os.path.exists` move to
  `mcp_tools_py.utils.python_environment.os.name` /
  `mcp_tools_py.utils.python_environment.os.path.exists`. These work because the
  ALGORITHM above calls `os.path.exists`, not `Path.exists()` — if the implementation
  drifts to `Path.exists()`, these patches become silent no-ops and the tests stop
  exercising the branch they name.
- `test_all_tools_missing` (`:134`), `test_lint_imports_unavailable_when_no_venv`
  (`:167`) and `test_vulture_unavailable_when_no_venv` (`:226`) assert the defect. Rewrite
  them to be deterministic under the new rule: pass `python_executable` pointing into an
  empty `tmp_path` so `binary()` genuinely misses, and keep the `False` assertions.
- `TestResolvePythonExecutable` **cannot** keep its current expected values.
  `_resolved_python` is now `str(Path(...))`, which `Path` normalises; the tests compare
  against `os.path.join(...)` output, which does not normalise the leading separator:

  | Test | Today's expected | New value on Windows |
  |---|---|---|
  | `:43-44` `test_venv_path_windows` | `os.path.join("/my/venv","Scripts","python.exe")` → `/my/venv\Scripts\python.exe` | `\my\venv\Scripts\python.exe` |
  | `:60-61` `test_venv_path_unix` | `os.path.join("/my/venv","bin","python")` | posix-only test, unchanged |
  | `:90` `test_python_executable_fallback` | `"/usr/local/bin/python3.11"` | `\usr\local\bin\python3.11` |
  | `:103` `test_sys_executable_fallback` | `sys.executable` | unchanged — already normalised |
  | `:521` `test_resolved_python_passed_to_pytest_runner` (in `TestToolHandlerShortCircuit`) | `"/custom/python"` | `\custom\python` |

  Rewrite `:43-44`, `:60-61` and `:90` to assert on the `Path` rather than the string,
  which is platform-normalised on both sides and states the intent:
  `assert server.environment.interpreter == Path("/my/venv") / "Scripts" / "python.exe"`,
  and `== Path("/usr/local/bin/python3.11")` for `:90`. Leave `:103` alone.

  `:521` is the same break outside `TestResolvePythonExecutable` and is easy to miss:
  `test_resolved_python_passed_to_pytest_runner` constructs the server with
  `python_executable="/custom/python"` and then asserts
  `call_kwargs.kwargs["python_executable"] == "/custom/python"` on top of the
  `== server._resolved_python` assertion at `:520`. The literal goes red on Windows in
  **this** step; step 6 only rewrites `:520`'s right-hand side. Change `:521` to
  `== str(Path("/custom/python"))`, keeping the test's point — the *resolved* interpreter,
  not the raw argument, reaches the runner.

`tests/test_code_checker/test_runners.py:229` — the positional `None,  # venv_path`
becomes `None,  # bin_dir`. Three further keyword call sites in the same file.

`tests/test_server_params.py:83` — `mock_check_pytest.assert_called_once_with(...)` lists
`venv_path=None`. It becomes `bin_dir=_server.environment.bin_dir`, and the value is no
longer `None`: with no flags set the interpreter is `sys.executable`, so `bin_dir` is
`Path(sys.executable).parent`. Assert against `_server.environment.bin_dir` rather than a
literal, matching how the same call already asserts `python_executable`.

Add one test asserting `run_tests` prepends `bin_dir` to `PATH` when given and leaves
`PATH` untouched when `None`.

## Checks

`run_format_code`, then `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])`,
`run_mypy_check`. Also `run_lint_imports_check` and `run_tach_check` — `utils` gains a
module but no new dependency edge, so both should stay green. And `run_vulture_check`,
which is what confirms the two whitelist entries were safe to drop.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`, then implement step 1.
> Write `tests/test_python_environment.py` first and watch it fail, then add
> `src/mcp_tools_py/utils/python_environment.py`, then rewire `server.py`,
> `code_checker_pytest/runners.py`, `checker_tools/pytest_tool.py` and `main.py`, then
> delete the now write-only `self.venv_path` / `self.python_executable` attributes with
> their `vulture_whitelist.py` entries and refresh the two flag docstrings, then fix
> the test churn listed in the step. This is one commit: tests, implementation and all
> checks passing. Do not touch `inspect_library.py` or `jedi_tools.py` — later steps own
> them.
