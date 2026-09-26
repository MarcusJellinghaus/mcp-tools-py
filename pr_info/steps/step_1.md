# Step 1 — tach, ruff, vulture and bandit resolve in the tool environment

Read [summary.md](./summary.md) first.

Scope: the console-script tools stop being looked for next to
`--python-executable` and are looked for next to `sys.executable` instead.

**lint-imports is deliberately left behind.** Its handler keeps taking the binary
from `context.environment`, and so do its availability answer and message —
`is_tool_available`/`unavailable_message` carve `lint-imports` out of this step's
tool-env routing below. All three (binary, answer, message) move together with the
`PYTHONPATH` bridge, in step 4. Running the tool env's lint-imports without that
bridge lets it resolve the root package from the tool env's own site-packages and
report PASSED on a stale installed copy — so no commit may leave it in that state.
Routing only the binary while leaving the answer/message on the tool env (the
original design) would also make `unavailable_message` name the tool env directory
and blame a broken mcp-tools-py install in the issue's own normal scenario (tool env
has the script, project env — expectedly — doesn't); the carve-out avoids that.

## WHERE

- `src/mcp_tools_py/utils/tool_context.py`
- `src/mcp_tools_py/utils/environment_info.py` — `TOOL_DISTRIBUTIONS`
- `src/mcp_tools_py/server.py`
- `src/mcp_tools_py/main.py`
- `src/mcp_tools_py/checker_tools/{tach,ruff_check,ruff_fix,vulture,bandit}_tool.py`
- `tests/conftest.py`, `tests/test_tool_context.py`,
  `tests/test_tool_availability/_helpers.py`,
  `tests/test_tool_availability/test_handler_short_circuit.py`,
  `tests/test_server_params.py`, `tests/test_checker_tools.py`,
  `tests/test_environment_info.py`,
  `tests/test_code_checker_bandit/test_integration.py`

## WHAT

```python
# utils/tool_context.py — new field, last in the dataclass
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ToolContext:
    project_dir: Path
    environment: PythonEnvironment
    test_folder: str = "tests"
    keep_temp_files: bool = False
    vulture_whitelist: str = "vulture_whitelist.py"
    check_timeout: Optional[int] = None
    tool_environment: PythonEnvironment = field(
        default_factory=PythonEnvironment.resolve
    )
```

Document it in the class docstring: "The environment mcp-tools-py itself runs in,
holding its console-script dependencies. Defaults to `sys.executable`'s
environment; not configurable from the CLI."

No other signature changes.

## HOW

1. **`is_tool_available`** — console-script branch only:
   `self.environment.binary(...)` → `self.tool_environment.binary(...)`,
   **except for `lint-imports`**, which keeps reading `self.environment`:

   ```python
   if tool_name in CONSOLE_SCRIPT_TOOLS:
       env = self.environment if tool_name == "lint-imports" else self.tool_environment
       available = env.binary(tool_name) is not None
       ...
   ```

   Step 4 deletes the `tool_name == "lint-imports"` branch once lint-imports' own
   binary lookup moves too, so the whole `CONSOLE_SCRIPT_TOOLS` set reads
   `self.tool_environment` uniformly. The `get_environment_info` branch below it is
   untouched.

2. **`unavailable_message`** — replace the console-script branch text, keeping
   `lint-imports` on the old wording until step 4:

   ```python
   if tool_name in CONSOLE_SCRIPT_TOOLS:
       if tool_name == "lint-imports":
           # Binary lookup hasn't moved yet (checker_tools/lint_imports_tool.py
           # still reads self.environment). Naming the tool env here would blame
           # a broken mcp-tools-py install when the tool env copy is the one
           # that exists. Step 4 deletes this branch once the binary moves too.
           return (
               f"{tool_name} is not available. No {tool_name} console script was "
               f"found in {self.environment.bin_dir}. Ensure --python-executable "
               f"points to an environment where {name} is installed. "
               f"That directory is re-checked on every call, so no restart is "
               f"needed after installing."
           )
       return (
           f"{tool_name} is not available. No {tool_name} console script was "
           f"found in {self.tool_environment.bin_dir}. {name} is a dependency "
           f"of mcp-tools-py, so its installation is incomplete: reinstall "
           f"mcp-tools-py and restart the server."
       )
   ```

   Drop the `--python-executable` sentence and the "no restart is needed" sentence
   for every console-script tool except `lint-imports`, which keeps both until
   step 4. Update the method docstring: it now promises the tool-env wording for
   four of the five console-script tools, and the old `--python-executable`
   wording for `lint-imports` until step 4 moves it too.

3. **`server.py`** — `_warn_missing_console_scripts` iterates
   `self.context.tool_environment.binary(key)` for every `CONSOLE_SCRIPT_TOOLS` key
   **except** `lint-imports`, which it still checks via
   `self.environment.binary(key)` — matching the `is_tool_available` carve-out above,
   so the startup warning and the runtime message never disagree about where
   lint-imports is expected. Its docstring notes the lint-imports exception. In both
   `ToolServer.__init__` and `create_server`, the `python_executable` docstring drops
   "and the checker tools" and gains: "The console-script tools ruff, bandit, vulture
   and tach come from mcp-tools-py's own environment instead; lint-imports moves
   there in a later step."

4. **`main.py`** — the `--python-executable` help text loses "and the checker tools"
   and gains one sentence: "ruff, bandit, vulture and tach come from mcp-tools-py's
   own environment and need not be installed here." lint-imports is left out of this
   sentence: it still needs to be installed in this environment until step 4.

5. **Four registrars** — one line each, e.g. in `tach_tool.py`:
   `tach_binary = context.tool_environment.binary("tach")`. Same for `ruff` (×2),
   `vulture` and `bandit`. Nothing else in these files moves.
   `lint_imports_tool.py` is **not** touched here — see the scope note above.

   Because `is_tool_available`/`unavailable_message` carve `lint-imports` out of the
   tool-env routing (HOW items 1-2), its availability answer, its message and its
   binary all keep reading `self.environment` in this commit — identical to today,
   with no skew between what is checked and what is reported. Step 4 deletes the
   carve-out and switches all three (answer, message, binary) to the tool env
   together with the `PYTHONPATH` bridge.

6. **`environment_info.py` — narrow `TOOL_DISTRIBUTIONS`.** It currently spans every
   key of `TOOL_MODULES`, so the startup line `_log_tool_versions` writes ("tool
   versions in \<project python\>: ...") reports the ruff/bandit/vulture/tach/
   import-linter copies found in the *project* interpreter — copies that, after this
   step, never run. Narrow it to the `python -m` tools, the only ones the probed
   interpreter still supplies:

   ```python
   # The distributions the `python -m` tools ship in, lowercased to match the blob.
   # The console-script tools are deliberately absent: they come from the tool env,
   # which this probe never describes.
   TOOL_DISTRIBUTIONS: tuple[str, ...] = tuple(
       TOOL_PACKAGES.get(key, key).lower()
       for key, module in TOOL_MODULES.items()
       if module is not None
   )
   ```

   Narrowed rather than re-targeted at the tool env: reporting the tool env's
   versions would mean a second probe subprocess at startup to restate
   mcp-tools-py's own pins, and `unavailable_message` already names the tool env
   directory when one of the five is missing.

## ALGORITHM

None — the change is a field lookup swap plus message text.

## DATA

`ToolContext.tool_environment: PythonEnvironment`, defaulting to
`PythonEnvironment.resolve()` (no arguments → `Path(sys.executable)`).
`unavailable_message` still returns `str`; `is_tool_available` still returns `bool`.

## TESTS (write first)

1. **`tests/test_tool_availability/_helpers.py`** — new seam. `PythonEnvironment.resolve()`
   reads `sys.executable`, so patching it gives the whole server a dummy tool env:

   ```python
   @contextlib.contextmanager
   def _patched_tool_env(tmp_path: Path, *scripts: str) -> Iterator[Path]:
       """Point PythonEnvironment.resolve() at a dummy tool env.

       Yields:
           The dummy tool env's script directory.
       """
       base = tmp_path / "toolenv"
       base.mkdir(exist_ok=True)
       interpreter = _dummy_python(base, *scripts)
       with patch.object(sys, "executable", interpreter):
           yield Path(interpreter).parent
   ```

2. **`tests/conftest.py`** — in the `tool_context` fixture build one
   `env = PythonEnvironment(Path(interpreter))` and pass it as both `environment`
   and `tool_environment`. Extend the docstring to say both point at the same
   directory, so a test makes a console-script tool unavailable by deleting its
   binary once.

3. **`tests/test_tool_context.py`**
   - `_context()` passes the dummy env as both fields.
   - New `TestConsoleScriptEnvironment`: a context whose `tool_environment` has
     `tach` and whose `environment` has none reports `is_tool_available("tach")`
     True; the mirror case (script only in `environment`) reports False.
   - `test_script_tool_message_reports_directory` (using `tach`, not `lint-imports`):
     assert the tool env's `bin_dir` is named, `"reinstall mcp-tools-py"` and
     `"restart the server"` appear, and `"--python-executable"` does **not**.
   - `test_lint_imports_message_still_names_project_env`: a context whose
     `tool_environment` has `lint-imports` and whose `environment` does not (the
     issue's own scenario) reports `is_tool_available("lint-imports")` **False**;
     `unavailable_message("lint-imports")` names `context.environment.bin_dir` (not
     the tool env), contains `"import-linter"` and `"--python-executable"`, and does
     **not** contain `"reinstall mcp-tools-py"` — the carve-out must stop the message
     from blaming a broken install when the tool env copy is the one that exists.
   - `test_unmapped_tool_installs_under_its_own_name`: assert
     `"ruff is a dependency"` (new tool-env wording, unmapped tool name).

4. **`tests/test_tool_availability/test_handler_short_circuit.py`**
   - `test_lint_imports_unavailable_returns_error`: build the server inside
     `_patched_tool_env(tmp_path, "lint-imports")` — tool env **has** the script,
     matching the issue's own scenario — with `python_executable` pointing at a
     script-less project env, and assert the message names the **project** env
     directory, contains `"--python-executable"`, and does **not** contain
     `"reinstall mcp-tools-py"`: the tool env having the script must not make the
     message blame a broken mcp-tools-py install while lint-imports' binary lookup
     is still deferred.
   - New `test_console_script_runs_from_tool_env`: build the server inside
     `_patched_tool_env(tmp_path, "tach")` with `python_executable` pointing at a
     script-less project env; with
     `mcp_tools_py.checker_tools.tach_tool.run_tach` patched to `"ok"`,
     `tools["run_tach_check"]()` returns `"ok"`.

5. **`tests/test_server_params.py::TestStartupConsoleScriptWarnings`** — construct the
   server inside `_patched_tool_env(tmp_path)`; `test_warning_matches_handler_message`
   asserts `"import-linter"` for a tool other than lint-imports, e.g. `tach` (the
   "is installed" wording is gone for that tool). Add a sibling assertion that a
   missing-lint-imports startup warning (tool env and project env both lacking it)
   still uses the "is installed" / `--python-executable` wording, matching the
   carve-out.

6. **`tests/test_checker_tools.py`** — `_remove_console_script` and the tach
   assertion read `context.tool_environment.binary(...)`. Same path as before, so
   these are clarity edits, not behaviour changes.

7. **`tests/test_code_checker_bandit/test_integration.py`** —
   `test_bandit_not_available_message` asserts `"no restart is needed" in result`,
   which is exactly the sentence HOW item 2 deletes. Replace that assertion with the
   new wording (`"reinstall mcp-tools-py"`, `"restart the server"`) and keep
   `"bandit is not available"`. The binary deletion itself stands: the fixture backs
   both environments with the same directory, so unlinking once still makes bandit
   unavailable.

8. **`tests/test_environment_info.py::TestToolVersionLogging`** —
   `test_success_logs_every_found_distribution` feeds a blob holding `pylint` and
   `import-linter` and asserts both are named. With `TOOL_DISTRIBUTIONS` narrowed,
   `import-linter` is no longer reported: assert `"pylint 3.2.0"` is named and
   `"import-linter"` is **not**, which is the regression test for the narrowing.

## VERIFY

`run_format_code`, then `run_pylint_check`, `run_pytest_check` with
`["-n", "auto"]`, `run_mypy_check`.

Do **not** treat the MCP `run_tach_check` / `run_ruff_check` tools as evidence:
this session's server process was started from the pre-edit modules and will not
import the change, so those calls exercise the old lookup whatever the result.
The new lookup is covered by the tests above. For a manual end-to-end look, start
a fresh server process instead — `mcp-tools-py --project-dir . --python-executable
<interpreter of a venv without tach>` — and confirm its startup warnings no longer
name tach, ruff, vulture or bandit. A lint-imports warning, if that venv also lacks
it, is expected and keeps the old "--python-executable" wording — it hasn't moved
yet.

Commit: `fix(tools): resolve console scripts in the tool env (#233)`

## LLM PROMPT

> Implement step 1 of issue #233. Read `pr_info/steps/summary.md` and
> `pr_info/steps/step_1.md` first. Write the tests listed under TESTS before the
> implementation, then make them pass. Keep the change to a field swap, message text
> and the `TOOL_DISTRIBUTIONS` narrowing — do not touch the `python -m` branch of
> `is_tool_available`, the cached environment probe's own logic, or
> `lint_imports_tool.py` itself. `lint-imports` must keep reading `self.environment`
> everywhere in this step — binary, availability answer and message are all carved
> out of the tool-env routing, and move to the tool env together with the
> `PYTHONPATH` bridge in step 4, not before. Finish with
> `run_format_code`, `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])`
> and `run_mypy_check`, all passing, then one commit.
