# Step 4 — lint-imports moves to the tool env with its `PYTHONPATH` bridge

Read [summary.md](./summary.md) and [step_3.md](./step_3.md) first — this step wires
in the helpers step 3 added.

Scope: lint-imports moves to the tool env **here**, together with the bridge that
makes the project's root package findable, and the `is_tool_available`/
`unavailable_message` carve-out that step 1 introduced for lint-imports is removed.
The move and the bridge land in one commit on purpose — the tool env's lint-imports
without the bridge silently checks an installed copy and reports PASSED on stale
code, so step 1 deliberately left the binary lookup alone, and step 3 deliberately
left the config/PYTHONPATH helpers unwired. Also drops the dead `root_package_paths`
line from this repo's `.importlinter`, which is the same subject: how the root
package is located.

## WHERE

- `src/mcp_tools_py/utils/tool_context.py` — remove the `lint-imports` carve-out in
  `is_tool_available` and `unavailable_message`
- `src/mcp_tools_py/server.py` — remove the `lint-imports` carve-out in
  `_warn_missing_console_scripts`
- `src/mcp_tools_py/code_checker_lint_imports/runners.py`
- `src/mcp_tools_py/checker_tools/lint_imports_tool.py` — binary lookup, impl call,
  and the `run_lint_imports_check` docstring's report contract
- `.importlinter`
- `tests/test_tool_context.py`, `tests/test_tool_availability/test_handler_short_circuit.py`,
  `tests/test_server_params.py` — delete or update the step-1 carve-out tests
- `tests/test_code_checker_lint_imports/test_runners.py`,
  `tests/test_code_checker_lint_imports/test_bridge_integration.py` (new),
  `tests/test_checker_tools.py`

## WHAT

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

That makes `run_lint_imports_check`'s own docstring wrong, and it must be fixed in
this commit. It currently promises callers:

> Structured report. The first non-empty line is the state header
> (PASSED / BROKEN / ERROR), so truncation cannot hide failures.

A stripped-flags info line already breaks that, but only when the caller passed
`-v`. The skipped-directory notice this step adds appears without the caller asking
for anything — an ordinary non-editable install of the project is enough — so a
caller that reads line one as the state header now mis-parses a normal run. State
the real contract:

```python
Returns:
    Structured report. Zero or more `[Info: ...]` lines come first,
    then the state header (PASSED / BROKEN / ERROR), so truncation
    cannot hide failures.
```

`run_lint_imports_check_impl`'s docstring says "either an info line (when flags were
stripped) or the state header"; drop the parenthesis, since stripped flags are no
longer the only reason for one.

## HOW

- **`tool_context.py`** — delete the `tool_name == "lint-imports"` branch added in
  step 1 from both `is_tool_available` and `unavailable_message`. Every
  `CONSOLE_SCRIPT_TOOLS` key, including `lint-imports`, now reads
  `self.tool_environment` uniformly, and every one gets the "is a dependency of
  mcp-tools-py ... reinstall and restart" wording. Restore the method docstrings to
  say this applies to all five.
- **`server.py`** — delete the `lint-imports` exception in
  `_warn_missing_console_scripts`; it now iterates
  `self.context.tool_environment.binary(key)` for all five keys, matching
  `is_tool_available`. Update the `python_executable` docstrings in
  `ToolServer.__init__`/`create_server` to name all five console-script tools
  together (drop the "lint-imports moves there in a later step" caveat step 1 added).
- **`runners.py`** imports `locate_packages` from
  `mcp_tools_py.utils.environment_info` (allowed: `code_checker_*` → `utils`) — the
  only new import; `_read_ini`/`_read_toml`/`_root_packages`/`_pythonpath_env` and the
  `info_lines`-carrying `_format_report` already exist from step 3.
- `lint_imports_tool.py` switches its binary lookup to
  `context.tool_environment.binary("lint-imports")` — the move deferred from steps 1
  and 3 — and calls the impl with keyword arguments, like the other five registrars:
  `lint_imports_binary=str(binary)` (tool env),
  `python_executable=str(context.environment.interpreter)` (project env). Its
  `run_lint_imports_check` docstring gets the corrected report contract above — info
  lines first, then the state header.
- `.importlinter`: delete `root_package_paths = src`. It is not an import-linter
  option and is silently ignored; the repo works because `mcp_tools_py` is installed
  editable.

## ALGORITHM

Inside `run_lint_imports_check_impl`, after building `info_lines` (step 3) and
`cleaned_args`:

```
names = _root_packages(project_dir, cleaned_args)
env = None
if names:
    located = locate_packages(python_executable, names)
    if isinstance(located, str):
        return f"=== ERROR: could not locate {', '.join(names)}: {located} ==="
    usable, skipped = located
    if skipped:
        info_lines.append(
            f"[Info: not added to PYTHONPATH, site-packages of the project "
            f"interpreter: {', '.join(skipped)} — lint-imports may be reading "
            f"an installed copy]"
        )
    env = _pythonpath_env(usable) if usable else None
result = execute_command(command, cwd=project_dir, timeout_seconds=..., env=env)
```

**Why the `skipped` filter exists, and why it asks about site directories rather
than about `--project-dir`.** A located directory that is a `site-packages` holds
the project pip-installed non-editable — and every other distribution in that
environment with it. Prepending it would put that whole directory ahead of the tool
env's `grimp` and `click`, and `grimp` ships a compiled extension, so a version or
ABI mismatch can crash the run. That is the one thing the issue rules out
explicitly.

"Is the directory under `--project-dir`?" does not answer that question. The
ordinary project venv lives *inside* the project — `<project>/.venv`, which is what
`${VIRTUAL_ENV}` usually points at — so for a non-editable install `locate_packages`
returns `<project>/.venv/Lib/site-packages`, a directory under `--project-dir` that
is exactly the kind that must never be prepended. Hence the predicate is "is this
one of the project interpreter's own site/purelib directories", answered by the
probe in step 2, and `--project-dir` does not enter into it. A located directory
that is *not* a site directory is a source tree, whichever side of the project root
it sits on, and prepending it is the whole point of the bridge.

What the filter does **not** do is make things safe: skipping leaves lint-imports
resolving the root package the way it would have without the bridge, which for a
project that is also installed in the tool env is exactly the stale-copy read this
step exists to prevent. (It is not "today's behaviour" — today lint-imports runs
from the *project* env, with the project's own `sys.path` underneath it.) So the
skip is never silent: it goes into the report as the info line above, ahead of the
state header, where a reader can see that a PASSED may not be about their working
tree.

## DATA

- `locate_packages` → `(usable, skipped)` on success; only `usable` is prepended,
  only `skipped` is reported. Nothing here re-tests the directories against
  `project_dir`.
- Locate failure → the single-line `=== ERROR: ... ===` form already used for
  timeouts, before any lint-imports subprocess runs.
- Everything else about the report is unchanged from step 3.

## TESTS (write first)

In `tests/test_code_checker_lint_imports/test_runners.py` (patch
`{MODULE_PATH}.locate_packages`, not `execute_command` — the locate call goes through
the `utils.environment_info` module):

1. `run_lint_imports_check_impl` behaviour, with `locate_packages` patched to return
   a `(usable, skipped)` tuple:
   - a usable directory reaches `execute_command` as `env={"PYTHONPATH": ...}`
     starting with that directory;
   - an existing `PYTHONPATH` (via `monkeypatch.setenv`) is appended after it,
     separated by `os.pathsep`;
   - a skipped directory produces `env is None` and a report carrying the
     `[Info: not added to PYTHONPATH, site-packages of the project interpreter`
     line naming that directory, above the state header. Spell the case out as the
     in-project-venv layout the predicate exists for: `project_dir=tmp_path`,
     `skipped=[str(tmp_path / ".venv" / "Lib" / "site-packages")]` — a directory
     *under* the project dir that must still be skipped, so a reviewer can see the
     old `is_relative_to(project_dir)` test would have prepended it;
   - a `(usable, skipped)` pair with one of each → `PYTHONPATH` holds only the usable
     directory, and the info line names only the skipped one;
   - `locate_packages` returning a string → the result starts with `=== ERROR:`,
     names the package, and `execute_command` is never called;
   - no config → `locate_packages` never called and `env` is `None`;
   - the existing `TestRunLintImportsCheckImpl` report/parsing tests keep passing with
     `python_executable=sys.executable` added to their calls. Their `project_dir`
     stays `"/project"`, which holds no config file, so `_root_packages` returns `[]`
     and neither `locate_packages` nor `PYTHONPATH` enters the picture.
2. `tests/test_checker_tools.py::test_lint_imports_passes_resolved_timeout` — assert
   on `call_args.kwargs["timeout_seconds"] == 120` and
   `call_args.kwargs["python_executable"] == str(tool_context.environment.interpreter)`,
   instead of the positional `call_args[0][3]`.

   Do **not** assert the binary against `tool_context.tool_environment.binary(...)`
   here: that fixture backs both environments with the same directory, so the two
   spellings produce the same string and the assertion would pass with the registrar
   left on `context.environment`. The switch needs a context where the two
   environments differ:

   ```python
   def test_lint_imports_binary_comes_from_the_tool_env(tmp_path: Path) -> None:
       """The script is taken from the tool env, not from --python-executable."""
       proj_base, tool_base = tmp_path / "projenv", tmp_path / "toolenv"
       proj_base.mkdir()
       tool_base.mkdir()
       project_env = PythonEnvironment(Path(_dummy_python(proj_base)))
       tool_env = PythonEnvironment(Path(_dummy_python(tool_base, "lint-imports")))
       context = ToolContext(
           project_dir=tmp_path,
           environment=project_env,
           tool_environment=tool_env,
       )
       ...
       assert mock_runner.call_args.kwargs["lint_imports_binary"] == str(
           tool_env.binary("lint-imports")
       )
   ```

   `_dummy_python` builds `<base>/scripts/`, so two bases give two directories. The
   project env holds no `lint-imports`, so a registrar still reading
   `context.environment.binary` gets `None`, short-circuits, and never calls the
   impl — which is what makes this test fail before the switch and pass after it.
3. **Remove or repurpose step 1's carve-out tests**, now that the carve-out is gone:
   - `tests/test_tool_context.py::test_lint_imports_message_still_names_project_env`
     is replaced by a test that lint-imports now behaves like the other four: a
     context whose `tool_environment` has `lint-imports` and whose `environment`
     does not reports `is_tool_available("lint-imports")` **True**, and
     `unavailable_message("lint-imports")` (when neither environment has it) names
     `tool_environment.bin_dir` and contains `"reinstall mcp-tools-py"`.
   - `tests/test_tool_context.py::TestUnavailableMessage::test_lint_imports_message_names_import_linter`
     predates step 1 and isn't one of its carve-out tests, but it breaks here anyway:
     it asserts `"import-linter is installed" in message`, which was true only
     because the carve-out kept lint-imports on the old `--python-executable`
     wording. Once this step deletes that carve-out, `unavailable_message("lint-imports")`
     uses the same tool-env template as the other four ("... {name} is a dependency
     of mcp-tools-py ... reinstall mcp-tools-py and restart the server"), which never
     contains "is installed". Update its assertion to `"import-linter is a dependency" in message`
     — mirroring step 1's
     `test_unmapped_tool_installs_under_its_own_name`, which asserts `"ruff is a
     dependency"` for the same template — and keep the existing `"lint-imports is
     not available"` assertion.
   - `tests/test_tool_availability/test_handler_short_circuit.py::test_lint_imports_unavailable_returns_error`
     is updated: `_patched_tool_env(tmp_path)` with no scripts now correctly produces
     a message naming the tool env directory (the carve-out that made this
     assertion wrong in step 1 is gone).
   - `tests/test_server_params.py::TestStartupConsoleScriptWarnings::test_lint_imports_warning_still_checks_project_env`
     (added in step 1) is inverted, not deleted: same asymmetric setup —
     `_patched_tool_env(tmp_path, "lint-imports")` (tool env has the script) with
     `python_executable` pointing at a script-less project env — but now asserts
     the startup warning list does **not** name lint-imports, since
     `_warn_missing_console_scripts` reads `tool_environment` for it too and finds
     it there. This is what proves `_warn_missing_console_scripts` itself was
     switched, not just `is_tool_available`/`unavailable_message`: the symmetric
     "both envs lack everything" scenario used by the plan's other
     `TestStartupConsoleScriptWarnings` tests would still warn correctly even if
     this carve-out were left in place by mistake, so it cannot catch a missed
     switch here.
4. **`tests/test_code_checker_lint_imports/test_bridge_integration.py`** (new file,
   every test `@pytest.mark.integration`). Everything above mocks the bridge; this
   is the one test that runs it. Nothing is patched — not `locate_packages`, not
   `execute_command`. Model it on `tests/test_target_scripts_contract.py`, which
   already drives the real tool-env binary.

   - Skip when `PythonEnvironment.resolve().binary("lint-imports")` is `None`.
   - Build a **src-layout** project under `tmp_path/proj`: `src/<pkg>/__init__.py`,
     `src/<pkg>/a.py` importing `<pkg>.b`, `src/<pkg>/b.py`, and a `.importlinter`
     with `root_package = <pkg>` plus one `forbidden` contract that `a -> b` breaks.
     Give `<pkg>` a unique suffix so it collides with nothing installed anywhere.
     It must not exist at the project root — only under `src/` — so lint-imports'
     own cwd entry cannot find it.
   - Build the *project interpreter*: `python -m venv tmp_path/venv`, then write a
     `.pth` file containing the absolute path of `tmp_path/proj/src` into that venv's
     site-packages (ask the new interpreter for the directory with
     `-c "import site; print(site.getsitepackages()[-1])"`). No pip, no network.
     The `.pth` points at a source tree, not at that `site-packages`, so the real
     probe reports `<tmp>/proj/src` as usable and the run exercises the prepend
     rather than the skip.
   - Call `run_lint_imports_check_impl(str(binary), str(project), extra_args=["--no-cache"],
     python_executable=<venv python>)` and assert the report is `BROKEN` and names
     the contract. `<pkg>` is importable by nothing but that venv, so a `BROKEN`
     verdict can only come from the config read, the real `locate` probe and the
     real `PYTHONPATH` handover having all worked.
   - Negative case, covering the silent-PASSED path directly: rewrite `.importlinter`
     to name a `root_package` no interpreter can find, and assert the report is
     **not** `PASSED` — lint-imports must surface its own "package not found" error
     rather than report green about code it never read.

## VERIFY

`run_format_code`, `run_pylint_check`, `run_pytest_check([\"-n\",\"auto\"])`,
`run_mypy_check`, then the new integration file:
`run_pytest_check(extra_args=["-n","auto",
"tests/test_code_checker_lint_imports/test_bridge_integration.py"],
markers=["integration"])`. That run is the evidence the bridge works; it is also
the only thing that would catch a stale-copy read.

The MCP `run_lint_imports_check` tool is **not** evidence here. This session's
server process was started from the pre-edit modules, so it still runs lint-imports
the old way — from the project env, with no bridge — and would report the four
contracts kept no matter what this step did to the code. Use it only to confirm the
`.importlinter` edit is harmless: removing `root_package_paths` must leave the four
contracts kept, which that (old) code path does test.

Commit: `fix(lint-imports): find the project's root package from the tool env (#233)`

## LLM PROMPT

> Implement step 4 of issue #233. Read `pr_info/steps/summary.md`,
> `pr_info/steps/step_3.md` and `pr_info/steps/step_4.md` first. Write the tests
> under TESTS before the implementation. Delete step 1's `lint-imports` carve-out in
> `tool_context.py` and `server.py` so all five console-script tools are routed
> uniformly. Keep the locate-failure path as a single `=== ERROR: ... ===` line that
> runs no subprocess. Do not import anything from `importlinter`, and do not put the
> project env's whole `sys.path` on `PYTHONPATH`. The new integration file must patch
> nothing — it is the only proof the bridge works. Finish with `run_format_code`,
> `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])`, `run_mypy_check`
> and the integration run named under VERIFY, all passing, then one commit.
