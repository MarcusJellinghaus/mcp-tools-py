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
- `src/mcp_tools_py/server.py` — `_resolve_python_executable`, `_check_tool_availability`
- `src/mcp_tools_py/code_checker_pytest/runners.py` — `run_tests`, `check_code_with_pytest`
- `src/mcp_tools_py/checker_tools/pytest_tool.py:111` — call site
- `src/mcp_tools_py/main.py:66-85` — both help strings
- `tests/test_tool_availability.py` — patch targets move; three assertions invert
- `tests/test_code_checker/test_runners.py:229` — positional comment

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
        if not p.exists(): raise FileNotFoundError(f"Python executable not found in virtual environment: {p}")
        return cls(p)
    return cls(Path(python_executable or sys.executable))

bin_dir:            return self.interpreter.parent
binary(name):       p = bin_dir / (f"{name}.exe" if os.name == "nt" else name)
                    return p if p.exists() else None
```

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

for name in CONSOLE_SCRIPT_TOOLS:
    path = self.environment.binary(name)
    availability[name] = path is not None
    setattr(self, f"_{name.replace('-', '_')}_binary", str(path) if path else None)
    if path is None:
        logger.warning("%s not found in %s. Ensure --venv-path or --python-executable "
                       "points to an environment where %s is installed.",
                       name, self.environment.bin_dir, name)
```

Update the `_check_tool_availability` docstring — it currently lists "(lint-imports,
vulture, ruff, bandit)" and omits tach.

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
  `mcp_tools_py.utils.python_environment.os...`.
- `test_all_tools_missing` (`:134`), `test_lint_imports_unavailable_when_no_venv`
  (`:167`) and `test_vulture_unavailable_when_no_venv` (`:226`) assert the defect. Rewrite
  them to be deterministic under the new rule: pass `python_executable` pointing into an
  empty `tmp_path` so `binary()` genuinely misses, and keep the `False` assertions.
- `TestResolvePythonExecutable` may keep asserting on `server._resolved_python`.

`tests/test_code_checker/test_runners.py:229` — the positional `None,  # venv_path`
becomes `None,  # bin_dir`. Three further keyword call sites in the same file.

Add one test asserting `run_tests` prepends `bin_dir` to `PATH` when given and leaves
`PATH` untouched when `None`.

## Checks

`run_format_code`, then `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])`,
`run_mypy_check`. Also `run_lint_imports_check` and `run_tach_check` — `utils` gains a
module but no new dependency edge, so both should stay green.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`, then implement step 1.
> Write `tests/test_python_environment.py` first and watch it fail, then add
> `src/mcp_tools_py/utils/python_environment.py`, then rewire `server.py`,
> `code_checker_pytest/runners.py`, `checker_tools/pytest_tool.py` and `main.py`, then fix
> the test churn listed in the step. This is one commit: tests, implementation and all
> checks passing. Do not touch `inspect_library.py` or `jedi_tools.py` — later steps own
> them.
