# Step 3 — lint-imports puts the project's root package on `PYTHONPATH`

Read [summary.md](./summary.md) first.

Scope: lint-imports now runs from the tool env (step 1), so the project's root
package must be made findable, or it silently checks an installed copy and reports
PASSED on stale code. Also drops the dead `root_package_paths` line from this repo's
`.importlinter`, which is the same subject: how the root package is located.

## WHERE

- `src/mcp_tools_py/code_checker_lint_imports/runners.py`
- `src/mcp_tools_py/checker_tools/lint_imports_tool.py`
- `.importlinter`
- `tests/test_code_checker_lint_imports/test_runners.py`, `tests/test_checker_tools.py`

## WHAT

```python
# code_checker_lint_imports/runners.py — new module-private helpers
_CONFIG_CANDIDATES: tuple[str, ...] = ("setup.cfg", ".importlinter", "pyproject.toml")

def _read_ini(path: Path) -> list[str]:      # [importlinter] root_package(s)
def _read_toml(path: Path) -> list[str]:     # [tool.importlinter] root_package(s)
def _root_packages(project_dir: str, extra_args: list[str]) -> list[str]:
def _pythonpath_env(directories: list[str]) -> dict[str, str]:
```

```python
# changed signature — python_executable is keyword-only and required
@log_function_call
def run_lint_imports_check_impl(
    lint_imports_binary: str,
    project_dir: str,
    extra_args: list[str] | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
    *,
    python_executable: str,
) -> str:
```

## HOW

- `runners.py` imports `locate_packages` from
  `mcp_tools_py.utils.environment_info` (allowed: `code_checker_*` → `utils`) and
  uses `configparser`, `tomllib`, `os` and `pathlib` from the stdlib. Do not import
  anything from `importlinter`.
- `lint_imports_tool.py` calls the impl with keyword arguments, like the other five
  registrars: `lint_imports_binary=str(binary)` (tool env, from step 1),
  `python_executable=str(context.environment.interpreter)` (project env).
- `.importlinter`: delete `root_package_paths = src`. It is not an import-linter
  option and is silently ignored; the repo works because `mcp_tools_py` is installed
  editable.

## ALGORITHM

Config discovery, mirroring the lint-imports CLI:

```
if "--config" in extra_args (or "--config=VALUE"):
    path = project_dir / value
    return _read_toml(path) if path.suffix == ".toml" else _read_ini(path)
for candidate in ("setup.cfg", ".importlinter", "pyproject.toml"):
    names = _read_toml/_read_ini(project_dir / candidate)   # by suffix
    if names: return names
return []
```

Each reader wraps everything in `try/except Exception`, logs at debug and returns
`[]`: a missing file, a missing `[importlinter]` / `[tool.importlinter]` section,
malformed TOML and a section without a root package are all "keep going". INI reads
`root_packages` as newline-separated, else `root_package`; TOML reads the list key,
else the scalar.

Inside `run_lint_imports_check_impl`, after `_strip_verbose_flags`:

```
names = _root_packages(project_dir, cleaned_args)
env = None
if names:
    located = locate_packages(python_executable, names)
    if isinstance(located, str):
        return f"=== ERROR: could not locate {', '.join(names)}: {located} ==="
    inside = [d for d in located if Path(d).resolve().is_relative_to(Path(project_dir).resolve())]
    env = _pythonpath_env(inside) if inside else None
result = execute_command(command, cwd=project_dir, timeout_seconds=..., env=env)
```

`_pythonpath_env` prepends rather than replaces, because `execute_command` merges the
dict over `os.environ` key by key:

```
existing = os.environ.get("PYTHONPATH")
parts = [*directories, existing] if existing else directories
return {"PYTHONPATH": os.pathsep.join(parts)}
```

## DATA

- `_root_packages` → `list[str]`, empty when nothing could be read.
- `_pythonpath_env` → `{"PYTHONPATH": "<dir>[<sep><dir>...][<sep><existing>]"}`.
- Locate failure → the single-line `=== ERROR: ... ===` form already used for
  timeouts, before any lint-imports subprocess runs.
- Everything else about the report is unchanged.

## TESTS (write first)

In `tests/test_code_checker_lint_imports/test_runners.py` (patch
`{MODULE_PATH}.locate_packages`, not `execute_command` — the locate call goes through
the `utils.environment_info` module):

1. `_root_packages`, against files written into `tmp_path`:
   - `.importlinter` with `root_package = pkg` → `["pkg"]`.
   - `setup.cfg` wins over a `.importlinter` naming a different package.
   - `pyproject.toml` with `[tool.importlinter] root_packages = ["a", "b"]` → `["a","b"]`.
   - `.importlinter` with a newline `root_packages` list → both names.
   - `--config custom.ini` and `--config custom.toml` in `extra_args` are honoured,
     resolved relative to the project dir.
   - no config file / no section / malformed TOML → `[]`.
2. `run_lint_imports_check_impl` behaviour, with `locate_packages` patched:
   - a located directory inside the project dir reaches `execute_command` as
     `env={"PYTHONPATH": ...}` starting with that directory;
   - an existing `PYTHONPATH` (via `monkeypatch.setenv`) is appended after it,
     separated by `os.pathsep`;
   - a located directory outside the project dir is skipped and `env` is `None`;
   - `locate_packages` returning a string → the result starts with `=== ERROR:`,
     names the package, and `execute_command` is never called;
   - no config → `locate_packages` never called and `env` is `None`;
   - the existing report/parsing tests keep passing with
     `python_executable=sys.executable` added to their calls.
3. `tests/test_checker_tools.py::test_lint_imports_passes_resolved_timeout` — assert
   on `call_args.kwargs["timeout_seconds"] == 120` and
   `call_args.kwargs["python_executable"] == str(tool_context.environment.interpreter)`
   instead of the positional `call_args[0][3]`.

## VERIFY

`run_format_code`, `run_pylint_check`, `run_pytest_check(["-n","auto"])`,
`run_mypy_check`, then `run_lint_imports_check` — it must still report the four
contracts as kept after `root_package_paths` is removed, which is the check that the
`PYTHONPATH` bridge works end to end.

Commit: `fix(lint-imports): find the project's root package from the tool env (#233)`

## LLM PROMPT

> Implement step 3 of issue #233. Read `pr_info/steps/summary.md` and
> `pr_info/steps/step_3.md` first. Write the tests under TESTS before the
> implementation. Keep the config readers failure-tolerant — any problem returns an
> empty list and lint-imports runs unchanged — and keep the locate-failure path as a
> single `=== ERROR: ... ===` line that runs no subprocess. Do not import anything
> from `importlinter`, and do not put the project env's whole `sys.path` on
> `PYTHONPATH`. Finish with `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n","auto"])`, `run_mypy_check` and
> `run_lint_imports_check`, all passing, then one commit.
