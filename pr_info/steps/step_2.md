# Step 2 — `probe.py locate` and `locate_packages()`

Read [summary.md](./summary.md) first.

Scope: the machinery for asking an interpreter where a package lives. Nothing calls
it yet — step 3 wires it into lint-imports.

## WHERE

- `src/mcp_tools_py/utils/target_scripts/probe.py`
- `src/mcp_tools_py/utils/environment_info.py`
- `tests/test_environment_info.py`

## WHAT

```python
# utils/target_scripts/probe.py
def _locate(names: list[str]) -> list[str]:
    """Directories to put on sys.path so each name in `names` is importable."""

_USAGE = (
    "usage: probe.py info [MODULE ...] | probe.py source IMPORT_PATH MAX_LINES"
    " | probe.py locate NAME [NAME ...]"
)
```

```python
# utils/environment_info.py
def locate_packages(interpreter: str, names: list[str]) -> list[str] | str:
    """Ask `interpreter` where each package in `names` lives.

    Returns:
        The directories to prepend to PYTHONPATH, or a string saying why the
        probe could not be trusted.
    """
```

## HOW

- `probe.py` stays standard-library-only (`os.path` and `json` are already fine
  under the `target-scripts-stdlib-only` contract). Add to `main`'s dispatch, before
  the `_USAGE` fallback:

  ```python
  if len(argv) >= 3 and argv[1] == "locate":
      json.dump(_locate(argv[2:]), sys.stdout)
      return 0
  ```

- `locate_packages` lives next to `probe_script_path()` and reuses it,
  `execute_command`, `PROBE_TIMEOUT_SECONDS` and `STDERR_SNIPPET`. It is **not**
  cached: the answer can change while the server runs.

## ALGORITHM

`_locate` (in the target interpreter):

```
for name in names:
    spec = find_spec(name)            # swallow any exception, skip the name
    if spec is None: continue
    locations = list(spec.submodule_search_locations or [])   # packages + namespace
    parents = [dirname(loc) for loc in locations] or (
        [dirname(spec.origin)] if spec.origin looks like a file else [])
    append each new, non-empty parent to an order-preserving result
```

`locate_packages` (in the server):

```
if not names: return []                       # no subprocess
result = execute_command([interpreter, probe_script_path(), "locate", *names],
                         timeout_seconds=PROBE_TIMEOUT_SECONDS)
if result.timed_out: return "probe of <interpreter> timed out after N seconds"
if execution_error or return_code: return "could not locate ...: <detail[:STDERR_SNIPPET]>"
parse JSON; if it is not a list of str: return "probe of <interpreter> returned unparsable output"
return the list
```

## DATA

- Probe stdout: a JSON array of directory strings, e.g.
  `["C:\\repo\\src"]`. Empty array when nothing resolves.
- `locate_packages` → `list[str]` on success, `str` (a reason) on failure. The
  caller distinguishes with `isinstance(..., str)`, as `resolve_target_directories`
  callers already do.

## TESTS (write first)

In `tests/test_environment_info.py`:

1. New `TestLocatePackages`, patching
   `mcp_tools_py.utils.environment_info.execute_command`:
   - JSON array → the same list back.
   - `timed_out=True` → a string containing `"timed out"` and the interpreter path.
   - `return_code=1, stderr="boom"` → a string containing `"boom"`.
   - stdout `"not json"` → a string containing `"unparsable"`.
   - `names=[]` → `[]` and `execute_command` never called.
   - A second call re-runs the subprocess (no caching).
2. In `TestProbeScript`, a real-subprocess test mirroring
   `test_real_child_reports_importability`: run
   `[sys.executable, probe_script_path(), "locate", "mcp_tools_py", "nosuchpkg_xyz"]`
   and assert the result is a one-element list whose entry is the directory holding
   the installed `mcp_tools_py` package — compare against
   `Path(mcp_tools_py.__file__).parent.parent`.

## VERIFY

`run_format_code`, `run_pylint_check`, `run_pytest_check(["-n","auto"])`,
`run_mypy_check`, plus `run_lint_imports_check` — the new probe code lives under
`target_scripts/`, so the stdlib-only contract must still pass.

Commit: `feat(probe): locate subcommand for finding a package's parent dir (#233)`

## LLM PROMPT

> Implement step 2 of issue #233. Read `pr_info/steps/summary.md` and
> `pr_info/steps/step_2.md` first. Write the tests under TESTS before the
> implementation. Keep `probe.py` standard-library-only and keep `locate_packages`
> uncached and small — no new module, no new dataclass. Nothing else may call the
> new code in this step. Finish with `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n","auto"])`, `run_mypy_check` and
> `run_lint_imports_check`, all passing, then one commit.
