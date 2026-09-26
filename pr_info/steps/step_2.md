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
def _locate(names: list[str]) -> dict[str, list[str]]:
    """Where each name in `names` lives, and this interpreter's site directories.

    The site directories are reported so the caller can tell a source tree
    from a `site-packages`, which must never go on PYTHONPATH.
    """

_USAGE = (
    "usage: probe.py info [MODULE ...] | probe.py source IMPORT_PATH MAX_LINES"
    " | probe.py locate NAME [NAME ...]"
)
```

```python
# utils/environment_info.py
def locate_packages(
    interpreter: str, names: list[str]
) -> tuple[list[str], list[str]] | str:
    """Ask `interpreter` where each package in `names` lives.

    Returns:
        `(usable, skipped)` — the directories to prepend to PYTHONPATH, and
        the located directories that are `interpreter`'s own site/purelib
        directories and must not be prepended.  Or a string saying why the
        probe could not be trusted.
    """
```

## HOW

- `probe.py` stays standard-library-only (`os.path`, `json`, `site` and `sysconfig`
  are all fine under the `target-scripts-stdlib-only` contract). Add to `main`'s
  dispatch, before the `_USAGE` fallback:

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
directories = []
for name in names:
    spec = find_spec(name)            # swallow any exception, skip the name
    if spec is None: continue
    locations = list(spec.submodule_search_locations or [])   # packages + namespace
    parents = [dirname(loc) for loc in locations] or (
        [dirname(spec.origin)] if spec.origin looks like a file else [])
    append each new, non-empty parent to `directories` (order-preserving)

site_dirs = sysconfig.get_paths()["purelib"], ["platlib"], plus
            site.getsitepackages()        # each call wrapped, de-duplicated,
                                          # empties dropped
return {"directories": directories, "site_dirs": site_dirs}
```

`locate_packages` (in the server):

```
if not names: return [], []                   # no subprocess
result = execute_command([interpreter, probe_script_path(), "locate", *names],
                         timeout_seconds=PROBE_TIMEOUT_SECONDS)
if result.timed_out: return "probe of <interpreter> timed out after N seconds"
if execution_error or return_code: return "could not locate ...: <detail[:STDERR_SNIPPET]>"
parse JSON; if it is not {"directories": [str], "site_dirs": [str]}:
    return "probe of <interpreter> returned unparsable output"
skipped = [d for d in directories if d is, or sits under, a site_dir]
usable  = [d for d in directories if d not in skipped]
return usable, skipped
```

The split lives here rather than in the caller: it is path normalisation
(`Path(d).resolve()`, then equality or `is_relative_to`) against an answer only the
probe can give, and every caller wants the same answer. Why a located
`site-packages` may never be prepended — and why "is it under `--project-dir`" is
the wrong question — is spelled out in step 3.

## DATA

- Probe stdout: a JSON object with two arrays of directory strings, e.g.
  `{"directories": ["C:\\repo\\src"], "site_dirs": ["C:\\venv\\Lib\\site-packages"]}`.
  `directories` is empty when nothing resolves; `site_dirs` describes the
  interpreter, not the request, so it is filled either way.
- `locate_packages` → `tuple[list[str], list[str]]` on success, `str` (a reason) on
  failure. The caller distinguishes with `isinstance(..., str)`, as
  `resolve_target_directories` callers already do, and unpacks otherwise.

## TESTS (write first)

In `tests/test_environment_info.py`:

1. New `TestLocatePackages`, patching
   `mcp_tools_py.utils.environment_info.execute_command`:
   - a `directories` entry under no `site_dirs` entry → `(["<dir>"], [])`.
   - a `directories` entry that *is* one of the `site_dirs` → `([], ["<dir>"])`.
   - a `directories` entry *inside* a `site_dirs` entry (the package's own
     subdirectory of `site-packages`, spelled with a different drive-letter case)
     → `([], ["<dir>"])`: the comparison resolves both sides.
   - a source dir and a site dir in one answer → each lands on its own side,
     order preserved.
   - `timed_out=True` → a string containing `"timed out"` and the interpreter path.
   - `return_code=1, stderr="boom"` → a string containing `"boom"`.
   - stdout `"not json"`, and a JSON array instead of the object → a string
     containing `"unparsable"`.
   - `names=[]` → `([], [])` and `execute_command` never called.
   - A second call re-runs the subprocess (no caching).
2. In `TestProbeScript`, a real-subprocess test mirroring
   `test_real_child_reports_importability`: run
   `[sys.executable, probe_script_path(), "locate", "mcp_tools_py", "nosuchpkg_xyz"]`
   and assert that exactly one directory came back — the one containing the
   installed `mcp_tools_py` package — and that `site_dirs` is non-empty.

   Assert on `usable + skipped`, not on `usable` alone: whether that directory is a
   `site-packages` depends on how `mcp_tools_py` is installed in the interpreter
   running the tests (editable here, non-editable in CI, which installs `.[dev]`),
   and the test must pass either way.

   Compare resolved `Path` objects, not the raw strings the probe emits:
   `Path(found).resolve() == Path(mcp_tools_py.__file__).resolve().parent.parent`.
   The probe returns whatever `os.path.dirname` produced in the child, whose
   drive-letter case and separators need not match this process's spelling.

## VERIFY

`run_format_code`, `run_pylint_check`, `run_pytest_check(["-n","auto"])`,
`run_mypy_check`.

The new probe code lives under `target_scripts/`, so the stdlib-only contract must
still hold. Check that with
`run_pytest_check(extra_args=["-n","auto","tests/test_target_scripts_contract.py"],
markers=["integration"])`, which builds a miniature package and runs the real
lint-imports against it. Do **not** rely on the MCP `run_lint_imports_check` tool
here: this session's server predates the edits, and until step 3 lands lint-imports
has no `PYTHONPATH` bridge, so a green answer from it would say nothing about the
code just written.

Commit: `feat(probe): locate subcommand for finding a package's parent dir (#233)`

## LLM PROMPT

> Implement step 2 of issue #233. Read `pr_info/steps/summary.md` and
> `pr_info/steps/step_2.md` first. Write the tests under TESTS before the
> implementation. Keep `probe.py` standard-library-only and keep `locate_packages`
> uncached and small — no new module, no new dataclass. Nothing else may call the
> new code in this step. Finish with `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n","auto"])`, `run_mypy_check` and the
> integration run named under VERIFY, all passing, then one commit.
