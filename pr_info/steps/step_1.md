# Step 1 — `PythonEnvironment` value object

#229 already derives tool detection from the resolved interpreter, so this step is no
longer a defect fix. It introduces the value object steps 3, 4 and 6 consume, moves the
two surviving `Scripts`/`bin` branches into it, and corrects the `main.py` help text.

**Acceptance criteria closed:** "Both surviving `Scripts`/`bin` branches live in one
module", "`main.py` help text no longer contradicts the resolution target".

Two pieces of the original step are already on main and must not be redone:

- **"With only `--python-executable` set, the console-script tools are found"** is
  delivered by #229 — `server.py:183` derives the search directory from the resolved
  interpreter, pinned by
  `tests/test_tool_availability/test_check_tool_availability.py:170`
  (`test_scripts_found_without_venv_path`).
- **Issue decision 22's `venv_bin` → `bin_dir` rename is dropped.** #229 already derives
  the value from the interpreter under the name `venv_bin`
  (`runners.py:89,200-203,475`), and `pytest_tool.py:107` passes
  `os.path.dirname(server._resolved_python)`. Renaming would churn `runners.py`,
  `pytest_tool.py`, `tests/test_code_checker/test_runners.py` and
  `tests/test_server_params.py` with no behaviour change, so decision 22 counts as
  satisfied.

## WHERE

**Created**
- `src/mcp_tools_py/utils/python_environment.py`
- `tests/test_python_environment.py`

**Modified**
- `src/mcp_tools_py/server.py` — `_resolve_python_executable` and `_script_path` move into
  `PythonEnvironment`; the dead `self.venv_path` / `self.python_executable` attributes go;
  the flag docstrings at `:82-93` (`ToolServer.__init__`) and `:297-307` (`create_server`)
- `vulture_whitelist.py:26-27` — the `_.python_executable` / `_.venv_path` entries
- `src/mcp_tools_py/main.py:70-78` — the `--python-executable` help string, and `:52-53` —
  the two epilog examples, which name a `tools-venv` path
- `tests/test_tool_availability/` — patch targets move; seven expected values change form;
  one assertion on a deleted attribute goes
- `tests/test_checker_tools.py:20` — the now-unread `server.venv_path` assignment

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

`venv_path` stays a parameter of `resolve()`. `--venv-path` is deprecated by #229 — hidden
from `--help` (`main.py:83`) and warned about (`main.py:197-202`) — but still resolves the
interpreter, and `tests/test_main_args.py:27,63` pin that. Honouring it here is the
transition path, not a new feature.

## ALGORITHM

```
resolve(python_executable, venv_path):
    if venv_path:
        sub = "Scripts" if os.name == "nt" else "bin"      # the ONE directory branch
        exe = "python.exe" if os.name == "nt" else "python"
        python, source = Path(venv_path) / sub / exe, "--venv-path"
    elif python_executable:
        python, source = Path(python_executable), "--python-executable"
    else:
        python, source = Path(sys.executable), "sys.executable"

    if not os.path.exists(python):
        on_path = shutil.which(str(python))
        if on_path is None:
            raise FileNotFoundError(
                f"Python interpreter not found: {python} (from {source})")
        return cls(Path(on_path))
    return cls(python)

bin_dir:            return self.interpreter.parent
binary(name):       p = bin_dir / (f"{name}.exe" if os.name == "nt" else name)
                    return p if os.path.exists(p) else None
```

**`resolve()` carries `_resolve_python_executable`'s current body verbatim**
(`server.py:118-150`): the existence check, the `shutil.which` PATH fallback for a bare
name, and the message `"Python interpreter not found: {python} (from {source})"` including
the `source` label. Three tests pin that contract —
`tests/test_tool_availability/test_resolve_python_executable.py:51`
(`match="--venv-path"`), `:64` (`match="--python-executable"`) and `:79` (asserts
`shutil.which` was called) — and a message without the source label fails the first two.

Existence is checked through `os.path.exists`, not `Path.exists()`, so that `os.name` and
the existence check share one patchable module attribute
(`mcp_tools_py.utils.python_environment.os`) — the idiom the existing availability tests
already use. Patching `Path.exists` globally would be the alternative; this is narrower.

`binary()` replaces `server._script_path` (`server.py:173-184`), whose `.exe` filename
branch at `:182` is the second and last `Scripts`/`bin` branch in the codebase. Both then
live in `python_environment.py`, which is what the criterion asks. It is a filename branch,
not a directory branch: `bin_dir` never branches.

## HOW — `server.py`

```python
self.environment = PythonEnvironment.resolve(python_executable, venv_path)
self._resolved_python = str(self.environment.interpreter)   # unchanged for callers
```

`_check_tool_availability` keeps its shape and its `_tool_binaries` dict; only the lookup
changes:

```python
path = self.environment.binary(key)
if path is not None:
    self._tool_binaries[key] = str(path)
else:
    logger.warning("%s", self.tool_unavailable_message(key))
availability[key] = path is not None
```

`_is_tool_available` and `tool_unavailable_message` likewise call
`self.environment.binary(...)` and `self.environment.bin_dir` in place of `_script_path`
and `os.path.dirname(self._resolved_python)`. Their message text and the fail-open probe
timeout are unchanged in this step — step 2 owns both.

`_is_tool_available` has a **second** `_tool_binaries` write, at `server.py:207`. It must
store `str(path)` too: `test_is_tool_available.py:77` asserts the stored value equals an
`os.path.join` string, so storing a `Path` fails. Both writes disappear in steps 2 and 6,
but step 1 has to land green on its own.

### Dead state to delete in the same commit

`self.python_executable` (`server.py:95`) and `self.venv_path` (`:96`) have exactly one
production reader between them, `_resolve_python_executable`, which moves out. The two
constructor **parameters** stay, but they are consumed by `PythonEnvironment.resolve(...)`
and stored nowhere else. So:

- Delete `self.python_executable = python_executable` and `self.venv_path = venv_path`.
  `self.environment` replaces both.
- Delete the `_.python_executable` and `_.venv_path` entries at `vulture_whitelist.py:26-27`,
  then run `run_vulture_check`. If vulture reports either name from a **different** source
  — `main.py:208-209` reads them off the argparse `Namespace` — restore just that entry
  with a comment naming the real reason, rather than restoring both blindly.
- Update the `venv_path` / `python_executable` docstrings in `ToolServer.__init__`
  (`:82-93`) and `create_server` (`:297-307`). Both currently describe an interpreter "for
  running tests"; it now also selects the environment that library and symbol lookups
  resolve in. Use the same wording as the `main.py` help string below.

Two test readers must move with it:

- `tests/test_tool_availability/test_handler_short_circuit.py:187` — #229 added
  `assert server.venv_path is None`. Delete that line; the test's actual subject is
  `venv_bin`, asserted at `:192-194`.
- `tests/test_checker_tools.py:20` sets `server.venv_path` on a `MagicMock`. `:187` above
  is its last reader, so once that goes the assignment is a write nobody reads and vulture
  flags it — CI runs `vulture src tests vulture_whitelist.py` (`ci.yml:154`). **Delete
  `:20` in this commit**, not in step 6's fixture migration.

### Dead imports to delete in the same commit

`server.py` loses its `os`, `shutil` and `sys` imports (`:4-6`) along with the two methods:

| Import | Only uses | Where they go |
|---|---|---|
| `sys` | `:141` | `python_environment.resolve` |
| `shutil` | `:144` | `python_environment.resolve` |
| `os` | `:133-136`, `:143`, `:182-184`, `:251` | `resolve` / `binary()`, and `:251` becomes `environment.bin_dir` |

Ruff and pylint flag the leftovers otherwise — the same reason step 2 drops the dead
`execute_command` import.

**The import removal and the patch-target repointing below are one commit.** A
`patch("mcp_tools_py.server.os.name")` against a module that no longer imports `os` raises
`AttributeError`, so leaving any of the ~20 sites behind turns the suite red.

## HOW — `main.py`

`main.py:70-78` says the flag "should point to the environment where they are installed
(the tool's own venv), not the project's runtime venv". Issue decision 5 says that is
backwards: pylint, pytest and mypy must import the project's dependencies, so the checker
venv and the project-dependency venv are necessarily the same one. Replace with wording
naming the **project** environment, e.g.:

> Path to the Python interpreter of the project's environment. The checkers run in it and
> library/symbol lookups resolve against it, so it must be the environment holding the
> project's dependencies and the checker tools. A path that neither exists nor resolves on
> PATH fails at startup. Defaults to the current interpreter (sys.executable).

The epilog carries the same framing as an example: `main.py:52-53` show
`--python-executable /path/to/tools-venv/bin/python` and
`C:\path\to\tools-venv\Scripts\python.exe`. Rename the path to a project venv
(`/path/to/project/.venv/bin/python`, `C:\path\to\project\.venv\Scripts\python.exe`).

`--venv-path` keeps `argparse.SUPPRESS` (`main.py:83`) and its deprecation warning
(`:197-202`): `tests/test_main_args.py:27` asserts the flag is absent from `--help` and
`:63` (`test_epilog_does_not_advertise_venv_path`) asserts the epilog names
`--python-executable` and not `--venv-path`. Both survive the rename — confirm by running
the file — but this edit must not break either.

`README.md` carries the same backwards framing in four more places — step 3 owns those.

## DATA

`PythonEnvironment.binary()` returns `Path | None` — `None` means "not present".
`resolve()` raises `FileNotFoundError` when the interpreter neither exists nor resolves on
PATH, preserving today's fail-loud server construction (`server.py:143-150`).

## Tests (write first)

`tests/test_python_environment.py` — pure unit tests, no subprocess:

1. `venv_path` wins over `python_executable`; patch
   `mcp_tools_py.utils.python_environment.os.name` to `"nt"` and `"posix"` and assert the
   two layouts (use `tmp_path` and create the file so `exists()` is true).
2. `venv_path` set but missing python → `FileNotFoundError` naming `--venv-path`.
3. Only `python_executable` set → used verbatim.
4. `python_executable` set but missing, and not on PATH → `FileNotFoundError` naming
   `--python-executable`.
5. A bare name resolves through `shutil.which`.
6. Neither set → `sys.executable`.
7. `bin_dir == interpreter.parent`, asserted by constructing `PythonEnvironment` directly
   (platform-independent).
8. `binary()` hit: create `tmp_path/ruff(.exe)` → returns that path. `binary()` miss:
   returns `None`.
9. With only `python_executable` pointing at `tmp_path/Scripts/python.exe` (or
   `bin/python`) and `tmp_path/.../ruff(.exe)` present, `binary("ruff")` is not `None` —
   #229's behaviour, restated against the value object.

`tests/test_tool_availability/` churn:

- **Patch targets.** Roughly fifteen sites patch `mcp_tools_py.server.os.name` or
  `.os.path.exists`: `test_resolve_python_executable.py:23,24,40,41,56,57,103`;
  `test_check_tool_availability.py:20,60,61,103,104-107,125,126`;
  `test_is_tool_available.py:204`; `test_handler_short_circuit.py:131,172`. Several patch a
  single `os.path.exists` so that both the interpreter *and* the console scripts appear to
  exist. One further site patches `shutil`:
  `test_resolve_python_executable.py:85` (`mcp_tools_py.server.shutil.which`), whose `:96`
  asserts `mock_which.assert_called_once_with("python3")` — it becomes
  `mcp_tools_py.utils.python_environment.shutil.which`. Because `_script_path` moves into
  `python_environment` alongside `resolve`, exactly one patch target survives:
  `mcp_tools_py.utils.python_environment.os.name` / `.os.path.exists`. These work only
  because the ALGORITHM above calls `os.path.exists`, not `Path.exists()` — if the
  implementation drifts, the patches become silent no-ops and the tests stop exercising the
  branch they name.
- **Expected values.** `_resolved_python` and the `_tool_binaries` values become
  `str(Path(...))`, which normalises the separator; the tests compare against `os.path.join`
  output and bare POSIX literals, which do not. CI is `ubuntu-latest`, so these bite the
  local Windows run first. On Windows:

  | Test | Today's expected | New value |
  |---|---|---|
  | `test_resolve_python_executable.py:31-32` `test_venv_path_windows` | `os.path.join("/my/venv","Scripts","python.exe")` → `/my/venv\Scripts\python.exe` | `\my\venv\Scripts\python.exe` |
  | `:48-49` `test_venv_path_unix` | `os.path.join("/my/venv","bin","python")` | posix-only test, unchanged |
  | `:95` `test_bare_name_resolved_on_path` | `"/usr/bin/python3"` | `\usr\bin\python3` |
  | `:113` `test_python_executable_fallback` | `"/usr/local/bin/python3.11"` | `\usr\local\bin\python3.11` |
  | `:126` `test_sys_executable_fallback` | `sys.executable` | unchanged — already normalised |
  | `test_handler_short_circuit.py:162` `test_resolved_python_passed_to_pytest_runner` | `"/custom/python"` | `\custom\python` |
  | `test_handler_short_circuit.py:194` `test_venv_bin_derived_from_resolved_python` | `"/custom"` | `\custom` |
  | `test_check_tool_availability.py:68-70` `test_lint_imports_available_when_binary_exists` | `os.path.join("/mock/venv","Scripts","lint-imports.exe")` → `/mock/venv\Scripts\lint-imports.exe` | `\mock\venv\Scripts\lint-imports.exe` |
  | `:133-135` `test_vulture_available_when_binary_exists` | the same for `vulture.exe` | `\mock\venv\Scripts\vulture.exe` |

  `test_check_tool_availability.py:188-190` is **safe** — its base comes from
  `os.path.dirname(python)` with `python` from `_dummy_python(tmp_path)`, already
  normalised on both sides.

  Rewrite the seven that break to assert on a `Path`, which is platform-normalised on both
  sides and states the intent:
  `assert server.environment.interpreter == Path("/my/venv") / "Scripts" / "python.exe"`,
  `== Path("/usr/bin/python3")` and `== Path("/usr/local/bin/python3.11")`. The two in
  `test_handler_short_circuit.py` compare strings against a mock's kwargs, so they become
  `== str(Path("/custom/python"))` and `== str(Path("/custom"))`; each keeps its point —
  the *resolved* interpreter, not the raw argument, is what reaches the runner. The two
  `_tool_binaries` assertions become
  `== str(Path("/mock/venv") / "Scripts" / "lint-imports.exe")` and the vulture equivalent.
  Leave `:48-49` and `:126` alone.

Already done by #229 — do **not** redo:

- `test_lint_imports_unavailable_when_no_venv` and `test_vulture_unavailable_when_no_venv`
  are now `test_lint_imports_unavailable_when_script_not_on_disk` and
  `test_vulture_unavailable_when_script_not_on_disk`
  (`test_check_tool_availability.py:73,137`), rewritten exactly as this step used to
  prescribe, using the new `_dummy_python` helper in
  `tests/test_tool_availability/_helpers.py`. Use `_dummy_python` for any new test needing
  a pinned script directory, in preference to patching `os.path.exists`.
- The `_check_tool_availability` docstring no longer omits tach (`server.py:152-157`).

## Checks

`run_format_code`, then `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])`,
`run_mypy_check`. Also `run_lint_imports_check` and `run_tach_check` — `utils` gains a
module but no new dependency edge, so both should stay green. And `run_vulture_check`,
which is what confirms the two whitelist entries were safe to drop.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`, then implement step 1.
> Write `tests/test_python_environment.py` first and watch it fail, then add
> `src/mcp_tools_py/utils/python_environment.py` carrying `_resolve_python_executable`'s
> body verbatim — existence check, `shutil.which` fallback and the exact error message —
> plus `_script_path` as `binary()`, then rewire `server.py` and `main.py`'s
> `--python-executable` help string and its two epilog examples, then delete the now
> write-only `self.venv_path` / `self.python_executable` attributes with their
> `vulture_whitelist.py` entries, drop `server.py`'s now-dead `os`, `shutil` and `sys`
> imports, and refresh the two flag docstrings, then fix the test churn listed in the step
> — the patch targets must be repointed in this same commit, or patching a removed module
> attribute raises `AttributeError`. Do **not** rename
> `venv_bin` to `bin_dir` and do not touch `code_checker_pytest/runners.py` — #229 already
> derives that value from the interpreter. Do not touch `inspect_library.py` or
> `jedi_tools.py` — later steps own them. This is one commit: tests, implementation and all
> checks passing.
