# Step 1 — Run every probe in a fresh temporary working directory

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_1.md`
> exactly. Follow TDD: write the tests first (part A), run them and see the
> new tests fail, then implement (part B) and docs (part C). Keep the
> change minimal; do not touch `target_scripts/probe.py` or any non-probe
> subprocess call. Run pylint, pytest (`-n auto`), mypy and lint-imports via the
> MCP tools; all must pass. Run `run_format_code`, then make exactly one commit.

## A. Tests first

### WHERE: `tests/conftest.py` — new fixture

```python
@pytest.fixture
def side_effect_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """A fake package that writes into its working directory when imported.
    Returns (fake_project, cwd_record)."""
```

ALGORITHM:
```
pkg = tmp_path / "fake_pkg"; create pkg/, pkg/sub/ (empty __init__.py), pkg/thing.py ("def thing() -> int:\n    return 42\n")
cwd_record = tmp_path / "cwd.txt"
pkg/__init__.py = "import os, pathlib\n"
                  "pathlib.Path('marker.txt').write_text('x', encoding='utf-8')\n"
                  f"pathlib.Path({str(cwd_record)!r}).write_text(os.getcwd(), encoding='utf-8')\n"
fake_project = tmp_path / "fake_project"; mkdir
monkeypatch.setenv("PYTHONPATH", str(tmp_path)); monkeypatch.chdir(fake_project)
return fake_project, cwd_record
```

DATA: `tuple[Path, Path]` — the directory that must stay untouched, and the
absolute file the import writes its working directory to. All files written
with `encoding="utf-8"`.

### WHERE: `tests/test_environment_info.py`

1. `TestResolveScope.test_package_scope_runs_the_scope_subcommand`: replace
   `mock_exec.assert_called_once_with(...)` with
   ```python
   mock_exec.assert_called_once()
   assert mock_exec.call_args.args[0] == [
       "/scope-pkg/python", str(probe_script_path()), "scope", "mypy"
   ]
   assert mock_exec.call_args.kwargs["timeout_seconds"] == PROBE_TIMEOUT_SECONDS
   ```
2. New test in `TestResolveScope`:
   ```python
   def test_dotted_scope_import_leaves_the_working_directory_untouched(
       self, side_effect_package: tuple[Path, Path]
   ) -> None:
   ```
   ```
   fake_project, cwd_record = side_effect_package
   resolution = resolve_scope(sys.executable, "fake_pkg.sub")
   assert resolution.error is None
   assert cwd_record.is_file()                       # the import really ran
   assert not (fake_project / "marker.txt").exists()
   assert not Path(cwd_record.read_text(encoding="utf-8")).exists()  # temp dir removed
   ```
   `side_effect_package` comes from `conftest.py` as a fixture; no import needed.
3. New class `TestRunProbeWorkingDirectory` with one parametrized mocked test
   proving all four probe callers run outside the current working directory:
   ```python
   @pytest.mark.parametrize(
       "call_probe",
       [
           lambda: _get_library_source("json.encoder", 50, "/cwd-source/python"),
           lambda: resolve_scope("/cwd-scope/python", "json"),
           lambda: locate_packages("/cwd-locate/python", ["json"]),
           lambda: get_environment_info("/cwd-info/python"),
       ],
       ids=["source", "scope", "locate", "info"],
   )
   def test_every_probe_runs_outside_the_working_directory(
       self, call_probe: Callable[[], object]
   ) -> None:
   ```
   ```
   with patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec:
       mock_exec.return_value = make_command_result(stdout="{}")
       call_probe()
   cwd = mock_exec.call_args.kwargs["cwd"]
   assert cwd
   assert Path(cwd) != Path(os.getcwd())
   ```
   `stdout="{}"` makes every caller take a non-raising path (unparsable blob
   for `info`/`locate`, a directory string for `scope`, verbatim source for
   `source`). New imports: `os`, `Callable` (`collections.abc`), and
   `_get_library_source` from `mcp_tools_py.inspect_library`.
4. Second test in `TestRunProbeWorkingDirectory`, guarding the cleanup flag the
   issue requires:
   ```python
   def test_temporary_directory_ignores_cleanup_errors(self) -> None:
   ```
   ```
   with (
       patch("mcp_tools_py.utils.environment_info.tempfile.TemporaryDirectory") as mock_tmp,
       patch("mcp_tools_py.utils.environment_info.execute_command") as mock_exec,
   ):
       mock_tmp.return_value.__enter__.return_value = "/probe-workdir"
       mock_exec.return_value = make_command_result()
       run_probe("/cleanup/python", "info")
   mock_tmp.assert_called_once_with(ignore_cleanup_errors=True)
   assert mock_exec.call_args.kwargs["cwd"] == "/probe-workdir"
   ```
   New import: `run_probe` from `mcp_tools_py.utils.environment_info`.

### WHERE: `tests/test_inspect_library.py`

1. In all six `TestChildProcess` tests, change the patch target
   `"mcp_tools_py.inspect_library.execute_command"` →
   `"mcp_tools_py.utils.environment_info.execute_command"`. Nothing else changes
   (`test_command_uses_the_given_interpreter` keeps reading `call_args.args[0]`).
2. New test in `TestChildProcess`:
   ```python
   def test_import_side_effects_stay_out_of_the_working_directory(
       self, side_effect_package: tuple[Path, Path]
   ) -> None:
   ```
   ```
   fake_project, cwd_record = side_effect_package
   result = _get_library_source("fake_pkg.thing", 200, sys.executable)
   assert "def thing" in result
   assert cwd_record.is_file()
   assert not (fake_project / "marker.txt").exists()
   assert not Path(cwd_record.read_text(encoding="utf-8")).exists()
   ```

Run the new tests now: both real-child tests must fail (marker lands in
`fake_project`), and all four parametrized cases must fail (no `cwd` kwarg).
`test_environment_info.py` fails at collection until `run_probe` exists
(import error); that counts as the expected red.

## B. Implementation

### WHERE: `src/mcp_tools_py/utils/environment_info.py`

HOW: add `import tempfile`; change the shim import to
`from mcp_tools_py.utils.subprocess_runner import CommandResult, execute_command`.

WHAT (place after `probe_script_path`):
```python
def run_probe(
    interpreter: str, *args: str, timeout_seconds: int = PROBE_TIMEOUT_SECONDS
) -> CommandResult:
```
Docstring: runs `probe.py` under `interpreter` in a fresh temporary working
directory, so import-time side effects of probed libraries never reach the
project; relative `PYTHONPATH` entries resolve against that directory; cleanup
failures are ignored. Args / Returns sections as in the rest of the module.

ALGORITHM:
```
with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as workdir:
    return execute_command(
        [interpreter, str(probe_script_path()), *args],   # positional
        cwd=workdir,
        timeout_seconds=timeout_seconds,
    )
```

Callers — replace each `execute_command([...], timeout_seconds=PROBE_TIMEOUT_SECONDS)`:
- `locate_packages`: `result = run_probe(interpreter, "locate", *names)`
- `resolve_scope`: `result = run_probe(interpreter, "scope", scope)`
- `get_environment_info`: `result = run_probe(interpreter, "info", *PROBED_MODULES)`

All result handling stays exactly as it is.

### WHERE: `src/mcp_tools_py/inspect_library.py`

- Imports: `from mcp_tools_py.utils.environment_info import STDERR_SNIPPET, run_probe`;
  remove the `execute_command` import (and `probe_script_path`).
- `_get_library_source`:
  ```python
  result = run_probe(
      interpreter, "source", import_path, str(max_lines),
      timeout_seconds=SOURCE_TIMEOUT_SECONDS,
  )
  ```
  Result handling unchanged.

DATA: `run_probe` returns the `CommandResult` from `execute_command` unchanged.

## C. Docs

- `docs/architecture/architecture.md`, `utils/target_scripts/probe.py` bullet:
  after "Executed under the *target* interpreter by absolute path", add that
  every run goes through `run_probe` in a fresh temporary working directory, so
  import-time side effects of probed libraries never land in the project, and
  relative `PYTHONPATH` entries resolve against that temporary directory.
- `README.md`, project-env paragraph (the one mentioning `get_library_source`):
  add one sentence — library lookups run in a throwaway working directory, so
  files a library writes on import don't land in your project, and relative
  `PYTHONPATH` entries are not resolved against the project.

## Checks and commit

- `run_pylint_check`, `run_pytest_check(extra_args=["-n", "auto"])`,
  `run_mypy_check`, `run_lint_imports_check` — all pass.
- `run_format_code`, then one commit, e.g.
  `fix(probe): run library probes in a temporary working directory (#288)`.
