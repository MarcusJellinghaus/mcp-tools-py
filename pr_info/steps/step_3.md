# Step 3 — lint-imports moves to the tool env with its `PYTHONPATH` bridge

Read [summary.md](./summary.md) first.

Scope: lint-imports moves to the tool env **here**, together with the bridge that
makes the project's root package findable. The two land in one commit on purpose —
the tool env's lint-imports without the bridge silently checks an installed copy and
reports PASSED on stale code, so step 1 deliberately left the binary lookup alone.
Also drops the dead `root_package_paths` line from this repo's `.importlinter`,
which is the same subject: how the root package is located.

## WHERE

- `src/mcp_tools_py/code_checker_lint_imports/runners.py`
- `src/mcp_tools_py/checker_tools/lint_imports_tool.py`
- `.importlinter`
- `tests/test_code_checker_lint_imports/test_runners.py`,
  `tests/test_code_checker_lint_imports/test_bridge_integration.py` (new),
  `tests/test_checker_tools.py`

## WHAT

```python
# code_checker_lint_imports/runners.py — new module-private helpers
_CONFIG_CANDIDATES: tuple[str, ...] = ("setup.cfg", ".importlinter", "pyproject.toml")

# None = this file has no import-linter section (or cannot be read); [] = it has
# one but names no root package.  The distinction is what stops discovery at the
# right file — see ALGORITHM.
def _read_ini(path: Path) -> list[str] | None:   # [importlinter] root_package(s)
def _read_toml(path: Path) -> list[str] | None:  # [tool.importlinter] root_package(s)
def _root_packages(project_dir: str, extra_args: list[str]) -> list[str]:
def _pythonpath_env(directories: list[str]) -> dict[str, str]:
```

```python
# _format_report's last parameter carries more than one line now
def _format_report(..., info_lines: list[str]) -> str:   # was info_line: str | None
```

The stripped-flags notice becomes the first entry of that list; the skipped-directory
notice of the ALGORITHM section is the second. Both still precede the state header,
so "the first non-empty line is an info line or the header" keeps holding.

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
- `lint_imports_tool.py` switches its binary lookup to
  `context.tool_environment.binary("lint-imports")` — the move deferred from step 1 —
  and calls the impl with keyword arguments, like the other five registrars:
  `lint_imports_binary=str(binary)` (tool env),
  `python_executable=str(context.environment.interpreter)` (project env).
- `.importlinter`: delete `root_package_paths = src`. It is not an import-linter
  option and is silently ignored; the repo works because `mcp_tools_py` is installed
  editable.

## ALGORITHM

Config discovery, mirroring the lint-imports CLI:

```
if "--config" in extra_args (or "--config=VALUE"):
    path = project_dir / value
    return (_read_toml if path.suffix == ".toml" else _read_ini)(path) or []
for candidate in ("setup.cfg", ".importlinter", "pyproject.toml"):
    names = _read_toml/_read_ini(project_dir / candidate)   # by suffix
    if names is not None: return names          # first file WITH the section wins
return []
```

Discovery stops at the first candidate that *has* an import-linter section, even
when that section names no root package — that is the file the CLI opens, and
falling through to the next one would read a file lint-imports never looks at and
put someone else's package on `PYTHONPATH`. Hence `is not None` rather than a
truthiness test: `None` means "no section here, keep looking", `[]` means "this is
the config, and it named nothing".

Each reader wraps everything in `try/except Exception`, logs at debug and returns
`None`: a missing file, a missing `[importlinter]` / `[tool.importlinter]` section
and malformed TOML are all "keep going". A section that parses but names no root
package returns `[]`. INI reads `root_packages` as newline-separated, else
`root_package`; TOML reads the list key, else the scalar. Either way `_root_packages`
hands back a plain `list[str]`, empty when nothing could be read.

Inside `run_lint_imports_check_impl`, after `_strip_verbose_flags`:

```
info_lines = ["[Info: stripped --verbose/-v from extra_args]"] if stripped else []
names = _root_packages(project_dir, cleaned_args)
env = None
if names:
    located = locate_packages(python_executable, names)
    if isinstance(located, str):
        return f"=== ERROR: could not locate {', '.join(names)}: {located} ==="
    root = Path(project_dir).resolve()
    inside = [d for d in located if Path(d).resolve().is_relative_to(root)]
    outside = [d for d in located if d not in inside]
    if outside:
        info_lines.append(
            f"[Info: not added to PYTHONPATH, outside --project-dir: "
            f"{', '.join(outside)} — lint-imports may be reading an installed copy]"
        )
    env = _pythonpath_env(inside) if inside else None
result = execute_command(command, cwd=project_dir, timeout_seconds=..., env=env)
```

**Why the `outside` filter exists.** A located directory outside the project is a
whole `site-packages` (the project pip-installed non-editable into its own venv).
Prepending it would put that entire directory ahead of the tool env's `grimp` and
`click` — and `grimp` ships a compiled extension, so a version or ABI mismatch can
crash the run. That is the one thing the issue rules out explicitly, so the filter
stays.

What the filter does **not** do is make things safe: skipping leaves lint-imports
resolving the root package the way it would have without the bridge, which for a
project that is also installed in the tool env is exactly the stale-copy read this
step exists to prevent. (It is not "today's behaviour" — today lint-imports runs
from the *project* env, with the project's own `sys.path` underneath it.) So the
skip is never silent: it goes into the report as the info line above, ahead of the
state header, where a reader can see that a PASSED may not be about their working
tree.

`_pythonpath_env` prepends rather than replaces, because `execute_command` merges the
dict over `os.environ` key by key:

```
existing = os.environ.get("PYTHONPATH")
parts = [*directories, existing] if existing else directories
return {"PYTHONPATH": os.pathsep.join(parts)}
```

## DATA

- `_read_ini` / `_read_toml` → `list[str] | None`; `None` means "no import-linter
  section here".
- `_root_packages` → `list[str]`, empty when nothing could be read.
- `_pythonpath_env` → `{"PYTHONPATH": "<dir>[<sep><dir>...][<sep><existing>]"}`.
- Locate failure → the single-line `=== ERROR: ... ===` form already used for
  timeouts, before any lint-imports subprocess runs.
- Info lines → `list[str]`, rendered above the state header as before.
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
   - a `setup.cfg` carrying an `[importlinter]` section that names no root package,
     next to a `.importlinter` that names `pkg` → `[]`, not `["pkg"]`: discovery
     stops at the file the CLI would open.
2. `run_lint_imports_check_impl` behaviour, with `locate_packages` patched:
   - a located directory inside the project dir reaches `execute_command` as
     `env={"PYTHONPATH": ...}` starting with that directory;
   - an existing `PYTHONPATH` (via `monkeypatch.setenv`) is appended after it,
     separated by `os.pathsep`;
   - a located directory outside the project dir is skipped, `env` is `None`, and
     the report carries the `[Info: not added to PYTHONPATH, outside --project-dir`
     line naming that directory, above the state header;
   - `locate_packages` returning a string → the result starts with `=== ERROR:`,
     names the package, and `execute_command` is never called;
   - no config → `locate_packages` never called and `env` is `None`;
   - the existing `TestRunLintImportsCheckImpl` report/parsing tests keep passing with
     `python_executable=sys.executable` added to their calls. Their `project_dir`
     stays `"/project"`, which holds no config file, so `_root_packages` returns `[]`
     and neither `locate_packages` nor `PYTHONPATH` enters the picture.
3. **The `_format_report` signature change reaches the tests that call it directly.**
   Eight tests in the same file (`tests/test_code_checker_lint_imports/test_runners.py`,
   roughly lines 247-345: `test_passed_header_first_line`,
   `test_info_line_appears_above_header`, `test_summary_line_when_present`,
   `test_broken_state_lists_contracts`, `test_warnings_listed`,
   `test_error_state_no_summary_no_broken_list`,
   `test_line_cap_appends_truncation_marker`, `test_empty_body_substituted`) pass
   `info_line=None` or `info_line="[Info: stripped ...]"` as a keyword. Each becomes
   `info_lines=[]` / `info_lines=["[Info: stripped ...]"]`, and
   `test_info_line_appears_above_header` gains a sibling proving two info lines both
   render, in order, above the state header.
4. `tests/test_checker_tools.py::test_lint_imports_passes_resolved_timeout` — assert
   on `call_args.kwargs["timeout_seconds"] == 120` and
   `call_args.kwargs["python_executable"] == str(tool_context.environment.interpreter)`,
   instead of the positional `call_args[0][3]`.

   Do **not** assert the binary against `tool_context.tool_environment.binary(...)`
   here: that fixture backs both environments with the same directory, so the two
   spellings produce the same string and the assertion would pass with the registrar
   left on `context.environment`. The switch needs a context where the two
   environments differ, mirroring step 1's `test_console_script_runs_from_tool_env`:

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

5. **`tests/test_code_checker_lint_imports/test_bridge_integration.py`** (new file,
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

`run_format_code`, `run_pylint_check`, `run_pytest_check(["-n","auto"])`,
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

> Implement step 3 of issue #233. Read `pr_info/steps/summary.md` and
> `pr_info/steps/step_3.md` first. Write the tests under TESTS before the
> implementation. Keep the config readers failure-tolerant — any problem returns an
> empty list and lint-imports runs unchanged — and keep the locate-failure path as a
> single `=== ERROR: ... ===` line that runs no subprocess. Do not import anything
> from `importlinter`, and do not put the project env's whole `sys.path` on
> `PYTHONPATH`. The new integration file must patch nothing — it is the only proof
> the bridge works. Finish with `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n","auto"])`, `run_mypy_check` and the integration
> run named under VERIFY, all passing, then one commit.
