# Step 3 — lint-imports config/PYTHONPATH helpers (unwired)

Read [summary.md](./summary.md) first.

Scope: the pure pieces lint-imports' tool-env move needs — reading the root
package(s) out of an import-linter config, and building a `PYTHONPATH` dict from a
list of directories — plus a behaviour-neutral refactor of `_format_report` to carry
more than one info line. **Nothing added here is called by anything yet.**
`lint_imports_tool.py`'s registrar keeps taking the binary from `context.environment`
(unchanged from today), and `run_lint_imports_check_impl`'s public signature and
behaviour are untouched. Step 4 wires these helpers in, switches the registrar to
the tool env, and lands the `PYTHONPATH` bridge, all in one commit — that is the one
"no commit may leave lint-imports tool-env-resolving without the bridge" applies to.
This step cannot violate that rule because it does not touch the tool env, the
registrar, or what lint-imports actually runs.

## WHERE

- `src/mcp_tools_py/code_checker_lint_imports/runners.py`
- `tests/test_code_checker_lint_imports/test_runners.py`

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

None of `_read_ini`, `_read_toml`, `_root_packages` or `_pythonpath_env` is called by
`run_lint_imports_check_impl` or anything else in this step — that wiring is step 4.
The `_format_report` change *is* wired in this step, because it is behaviour-neutral:
`run_lint_imports_check_impl` already builds a single optional info line (for a
stripped `--verbose`/`-v`), so its body changes to build a one-item-or-empty list and
pass `info_lines=` instead of `info_line=`, producing an identical report either way.

## HOW

- `runners.py` uses `configparser`, `tomllib`, `os` and `pathlib` from the stdlib for
  the new helpers. Do not import anything from `importlinter`.
- Inside `run_lint_imports_check_impl`, change only the `info_line` variable and the
  `_format_report` call:

  ```python
  info_lines = ["[Info: stripped --verbose/-v from extra_args]"] if stripped else []
  ...
  return _format_report(state, summary, broken_contracts, warnings, combined, info_lines)
  ```

  Nothing else in the function changes: no new parameter, no call to `_root_packages`
  or a `locate` probe, no `env=` on `execute_command`. Those land in step 4.

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
(once step 4 wires it in) put someone else's package on `PYTHONPATH`. Hence
`is not None` rather than a truthiness test: `None` means "no section here, keep
looking", `[]` means "this is the config, and it named nothing".

Each reader wraps everything in `try/except Exception`, logs at debug and returns
`None`: a missing file, a missing `[importlinter]` / `[tool.importlinter]` section
and malformed TOML are all "keep going". A section that parses but names no root
package returns `[]`. INI reads `root_packages` as newline-separated, else
`root_package`; TOML reads the list key, else the scalar. Either way `_root_packages`
hands back a plain `list[str]`, empty when nothing could be read.

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
- `_format_report`'s `info_lines: list[str]`, rendered above the state header, in
  order, exactly as the single `info_line` was.

## TESTS (write first)

In `tests/test_code_checker_lint_imports/test_runners.py`:

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
2. `_pythonpath_env`: one directory, no existing `PYTHONPATH` → `{"PYTHONPATH": dir}`;
   two directories → joined with `os.pathsep`, in order; an existing `PYTHONPATH`
   (via `monkeypatch.setenv`) is appended after the given directories, not before.
3. **The `_format_report` signature change reaches the tests that call it directly.**
   Eight tests in this file (roughly lines 247-345: `test_passed_header_first_line`,
   `test_info_line_appears_above_header`, `test_summary_line_when_present`,
   `test_broken_state_lists_contracts`, `test_warnings_listed`,
   `test_error_state_no_summary_no_broken_list`,
   `test_line_cap_appends_truncation_marker`, `test_empty_body_substituted`) pass
   `info_line=None` or `info_line="[Info: stripped ...]"` as a keyword. Each becomes
   `info_lines=[]` / `info_lines=["[Info: stripped ...]"]`, and
   `test_info_line_appears_above_header` gains a sibling proving two info lines both
   render, in order, above the state header.
4. The existing `TestRunLintImportsCheckImpl` report/parsing tests are unaffected by
   this step (they don't reference config files or `PYTHONPATH`) and keep passing
   unchanged — `_root_packages`/`_pythonpath_env` aren't called from
   `run_lint_imports_check_impl` yet.

## VERIFY

`run_format_code`, `run_pylint_check`, `run_pytest_check(["-n","auto"])`,
`run_mypy_check`. No integration test is needed: nothing in this step changes what
lint-imports actually runs or where its binary comes from, so there is nothing new
for an integration test to exercise yet — that arrives with the wiring in step 4.

Commit: `refactor(lint-imports): add config/PYTHONPATH helpers, not yet wired (#233)`

## LLM PROMPT

> Implement step 3 of issue #233. Read `pr_info/steps/summary.md` and
> `pr_info/steps/step_3.md` first. Write the tests under TESTS before the
> implementation. Keep the config readers failure-tolerant — any problem returns
> `None`/`[]` as specified. None of `_read_ini`, `_read_toml`, `_root_packages` or
> `_pythonpath_env` may be called from anywhere except their own tests — do not touch
> `lint_imports_tool.py`, `.importlinter`, or `run_lint_imports_check_impl`'s
> signature; only its `info_line` → `info_lines` variable and the `_format_report`
> call change, and the resulting report text must be identical to before. Finish with
> `run_format_code`, `run_pylint_check`, `run_pytest_check(extra_args=["-n","auto"])`
> and `run_mypy_check`, all passing, then one commit.
