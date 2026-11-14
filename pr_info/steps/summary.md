# Summary — #288 Library probes: import side effects write into the project root

## Problem

Every call of `target_scripts/probe.py` runs without `cwd`, so the child inherits
the server's working directory — usually the project root. Import-time code in a
probed library (e.g. chainlit creating `.chainlit/` and `.files/`) then writes
into the project. Affected probe modes:

| Caller | Probe mode | Runs import-time code? |
|---|---|---|
| `inspect_library._get_library_source` | `source` | Yes (`importlib.import_module`) |
| `environment_info.resolve_scope` | `scope` | Yes, for dotted names (`find_spec("a.b")` imports `a`) |
| `environment_info.locate_packages` | `locate` | Yes, for dotted names |
| `environment_info.get_environment_info` | `info` | No |

## Architectural / design changes

- **One shared entry point for every probe run:** a new
  `run_probe(interpreter, *args, timeout_seconds=PROBE_TIMEOUT_SECONDS)` in
  `src/mcp_tools_py/utils/environment_info.py`. It runs
  `[interpreter, str(probe_script_path()), *args]` with `cwd` set to a fresh
  `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)` and returns the
  `CommandResult`.
- **All four callers route through it** (`source`, `scope`, `locate`, `info`),
  so no current or future probe call can skip the protection. Each caller keeps
  its own result handling unchanged.
- `inspect_library` no longer imports `execute_command` or `probe_script_path`;
  it depends on `run_probe` instead.
- **Resolution is unaffected:** the probe runs by absolute path, so `sys.path[0]`
  is the script's directory, never the working directory.
- **Accepted behaviour change (documented, not worked around):** relative
  `PYTHONPATH` entries now resolve against the temp directory. Libraries that
  read config from the working directory at import time see their defaults.
- **Cleanup never fails a call:** `ignore_cleanup_errors=True` covers Windows
  grandchild processes holding the temp dir open.
- **Out of scope:** the probe script itself, and every other subprocess
  (pytest, mypy, ruff, coverage, rope, …) — they keep `cwd=project_dir` on purpose.

## Files

| File | Change |
|---|---|
| `src/mcp_tools_py/utils/environment_info.py` | Modify — add `run_probe`; route `locate_packages`, `resolve_scope`, `get_environment_info` through it |
| `src/mcp_tools_py/inspect_library.py` | Modify — route `_get_library_source` through `run_probe`; drop two imports |
| `tests/conftest.py` | Modify — add `side_effect_package` fixture |
| `tests/test_environment_info.py` | Modify — relax one assertion; add one real-child test; add one parametrized test that all four probe callers pass a temp `cwd` |
| `tests/test_inspect_library.py` | Modify — retarget six patch strings; add one real-child test |
| `docs/architecture/architecture.md` | Modify — `probe.py` bullet |
| `README.md` | Modify — one sentence in the project-env paragraph |

No files or folders are created.

## Steps

- [Step 1](./step_1.md) — `run_probe` with a temporary working directory, all four callers, tests, docs (one commit)

Manual acceptance (not automatable here, chainlit is not a dependency):
`get_library_source("chainlit.step.Step")` leaves the project directory unchanged.
