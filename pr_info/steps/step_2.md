# Step 2 — Rewrite `_is_tool_available`: fast path, 30s probe, fail open on timeout

Implements **Decisions 1 (lazy half), 3, 4, 5, 6, 7, 13**. See
[summary.md](./summary.md) §1-§4.

This is the fix for the reported symptom. Depends on Step 1.

## WHERE

| File | Change |
|---|---|
| `src/mcp_tools_py/server.py` | new module-level `_TOOL_MODULES`, `PROBE_TIMEOUT_SECONDS`; `self._tool_binaries` in `__init__`; new `ToolServer._script_path`; rewrite `_is_tool_available` (`:214-239`) |
| `tests/test_tool_availability.py` | `TestIsToolAvailable` |

If #227 (issue #219) has landed, `resolve_timeout` sits immediately after
`_is_tool_available` — **preserve it**. The probe keeps a plain `30`; #219 owns
timeout configurability and explicitly leaves this probe hardcoded.

## WHAT

```python
PROBE_TIMEOUT_SECONDS = 30

# Tool key -> module for `python -m <module>`, or None when the tool is only
# ever run through its console script. The console script is named after the key.
_TOOL_MODULES: dict[str, Optional[str]] = {
    "pytest": "pytest",
    "pylint": "pylint",
    "mypy": "mypy",
    "black": "black",
    "isort": "isort",
    "lint-imports": None,
    "vulture": None,
    "ruff": None,
    "bandit": None,
    "tach": None,
}


class ToolServer:
    def _script_path(self, key: str) -> Optional[str]:
        """Return the console-script path for `key` next to the resolved
        interpreter, or None when it is not there."""

    def _is_tool_available(self, tool_name: str) -> bool:
        """Check if a tool is available, probing on first call. ..."""
```

## HOW

- `_script_path` is the **only** place that joins a directory to a tool name and
  tests existence. Step 3 reuses it for the eager loop.
- `os.path.dirname(self._resolved_python)` is the search directory — never
  `venv_path`, never `parent.parent`.
- `os.path.exists` and `os.name`, not `pathlib` (see summary — 14 existing patch
  statements).
- Probe env: `execute_command(..., env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})`.
  `execute_command`'s `env` is additive (`prepare_env` merges over an `os.environ`
  copy), so `PATH` is not clobbered. Set uniformly on all probes — inert for the
  other four, and a per-tool exception costs more code than it saves.
- `lint-imports` reaching the `module is None` branch is unreachable in practice
  once Step 3 lands, because the eager loop always caches it first. Write the
  branch anyway: it is what makes the absence deliberate rather than accidental.
- **The fast path must record the binary for script-group keys.** When
  `_TOOL_MODULES[key] is None` and `_script_path(key)` returns a path, store it in
  `self._tool_binaries[key]` as well as setting `available = True`. Step 3 deletes
  the six `assert binary is not None` guards on the strength of "presence in
  `_tool_binaries` means available" (step_3.md:52); a script-group key that reaches
  `_is_tool_available` without being in `_tool_availability` would otherwise be
  reported available with no recorded path and `KeyError` at the run site.
  `_tool_binaries` therefore has to exist before Step 2's fast path can write to it
  — initialise it in `__init__` here rather than in Step 3.

## ALGORITHM

`_script_path`:

```
name = f"{key}.exe" if os.name == "nt" else key
path = os.path.join(os.path.dirname(self._resolved_python), name)
return path if os.path.exists(path) else None
```

`_is_tool_available`:

```
if tool_name in self._tool_availability: return self._tool_availability[tool_name]
script = self._script_path(tool_name)                      # cheapest check first
if script:
    available = True
    if _TOOL_MODULES.get(tool_name) is None:               # script group: record the path
        self._tool_binaries[tool_name] = script
else:
    module = _TOOL_MODULES.get(tool_name)
    if module is None: available = False                   # no probe possible
    else:
        r = execute_command([self._resolved_python, "-m", module, "--version"],
                            timeout_seconds=PROBE_TIMEOUT_SECONDS,
                            env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"})
        if r.timed_out: available = True                    # FAIL OPEN, log WARNING
        else: available = r.return_code == 0 and not r.execution_error
self._tool_availability[tool_name] = available
return available
```

**`timed_out` must be tested before the `return_code`/`execution_error` predicate.**
A timeout sets `execution_error` too, so the existing predicate already excludes
timeouts; placing the fail-open branch after it leaves that branch unreachable —
the code compiles, the existing tests pass, and the bug survives untouched.

## DATA

- `_TOOL_MODULES: dict[str, Optional[str]]`, module-level, ten entries.
- `_script_path` returns `Optional[str]` — an absolute path, or `None`.
- `_is_tool_available` returns `bool`; `self._tool_availability` stays
  `dict[str, bool]` (no tri-state).
- `self._tool_binaries: dict[str, str]` — created empty in `__init__` before
  `_check_tool_availability()` runs, written by the fast path for script-group keys
  only. Step 3 adds the eager loop as its second writer.

## LOGGING

- Timeout: `logger.warning` naming the timeout, the tool and `self._resolved_python`,
  and stating that the tool is assumed available.
- Success: keep today's `logger.info("%s version: %s", ...)` for the probe branch.
- Failure: `logger.warning` — the `--venv-path` wording in it is rewritten in Step 4;
  leaving it for now keeps this step to one concern.

## TESTS (write first)

In `tests/test_tool_availability.py::TestIsToolAvailable`. Add a small module-level
helper that builds a real script directory under `tmp_path` (a dummy `python.exe` /
`python` plus whichever console scripts a test wants) and returns a server built
with `python_executable=` that dummy. That pins the searched directory instead of
depending on the ambient interpreter, and needs no `os.path.exists` patching.

New tests:

1. `test_script_on_disk_skips_subprocess` — `pytest`(`.exe`) present in the script
   dir; `_is_tool_available("pytest")` is `True` and `execute_command` is not called.
2. `test_timeout_fails_open_and_caches` — probe returns
   `make_command_result(return_code=-1, timed_out=True, execution_error="Process timed out after 30 seconds")`;
   result is `True`, `_tool_availability["pytest"]` is `True`, and a second call
   makes no further subprocess call. Assert a WARNING is emitted (`caplog`).
3. `test_execution_error_without_timeout_caches_false` — `execution_error="spawn failed"`,
   `timed_out=False` → `False` and cached. Guards Decision 13.
4. `test_probe_disables_plugin_autoload` — inspect
   `mock_exec.call_args.kwargs["env"]` for `PYTEST_DISABLE_PLUGIN_AUTOLOAD == "1"`,
   and `timeout_seconds == 30`.
5. `test_script_only_tool_never_probes` — a key whose `_TOOL_MODULES` value is
   `None`, absent from `_tool_availability` and absent from the script dir →
   `False`, no subprocess.

**Rewrite** — two existing tests in this class break, for the same reason Step 3's
three do. They construct `_create_server(project_dir=Path("/project"))` with no
`python_executable`, so `_resolved_python` is `sys.executable` — the project's own
venv under test — and its script directory holds a real `pytest.exe`. The fast path
hits and the mocked probe is never called:

6. `test_first_call_runs_subprocess_and_caches` (`:247-268`) — `mock_exec.assert_called_once()`
   fails, because no subprocess runs at all.
7. `test_subprocess_failure_marks_unavailable` (`:307-327`) — asserts `False`, gets
   `True` from the fast path.

Move both onto the `tmp_path` script directory helper, with the directory left
empty, so the ambient interpreter cannot satisfy the fast path and each test still
exercises the probe branch it was written for. Do not simply re-point them.

`test_second_call_returns_cached_no_subprocess` and `test_eager_tool_returned_from_cache`
pre-seed `_tool_availability`, so the cache branch returns before the fast path and
they pass unchanged. `test_subprocess_success_marks_available` still asserts `True`,
but only by accident once the fast path hits — move it to the same helper so it
keeps testing the probe.

## LLM PROMPT

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`. Step 1 is done.
>
> Implement Step 2 only: in `src/mcp_tools_py/server.py`, add the module-level
> `_TOOL_MODULES` table and `PROBE_TIMEOUT_SECONDS = 30`, add
> `ToolServer._script_path(key)`, and rewrite `_is_tool_available` to check, in
> order: the cache, a console script sitting next to `_resolved_python`, then
> `python -m <module> --version` with `timeout_seconds=30` and
> `env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}`. A tool with `module=None` never
> probes and is unavailable.
>
> When the fast path finds a script for a `module=None` key, store the path in
> `self._tool_binaries[key]` as well as returning `True`. Initialise
> `self._tool_binaries: dict[str, str] = {}` in `__init__` before
> `_check_tool_availability()` is called. Step 3 deletes the
> `assert binary is not None` guards on the strength of "in `_tool_binaries` means
> available", so availability must never be `True` without a recorded path.
>
> The predicate order is load-bearing: test `result.timed_out` **first** and fail
> open on it (cache `True`, log a WARNING). A timeout also sets `execution_error`,
> so putting the fail-open branch after the `return_code == 0 and not
> execution_error` check would leave it unreachable while all tests still pass.
> A non-timeout `execution_error` still caches `False`.
>
> Use `os.path.exists` and `os.name`, not `pathlib` — existing tests patch
> `mcp_tools_py.server.os.path.exists` and `mcp_tools_py.server.os.name`.
>
> Write the tests first, using a `tmp_path` script directory rather than patching
> `os.path.exists`, so the searched directory is pinned and not the ambient
> interpreter's.
>
> Three existing tests in `TestIsToolAvailable` must move onto that helper, not just
> be re-pointed: `test_first_call_runs_subprocess_and_caches`,
> `test_subprocess_failure_marks_unavailable` and
> `test_subprocess_success_marks_available` build a server with no
> `python_executable`, so `_resolved_python` is `sys.executable` and its script
> directory holds a real `pytest.exe`. The fast path short-circuits, the mocked
> probe never runs, and the first two fail outright. An empty `tmp_path` script
> directory keeps all three exercising the probe branch.
>
> Do not touch `_check_tool_availability` (Step 3), any message wording (Step 4),
> or any `checker_tools/*` module. If `resolve_timeout` exists in `server.py`,
> preserve it — the probe keeps a plain `30`.
>
> While working, note (do not fix) how each probe-group tool degrades when the
> fail-open guess is wrong; report it in the commit message or chat.
>
> Then run, in order: `run_format_code`, `run_pylint_check`,
> `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`,
> `run_mypy_check`. All must pass. Commit as one commit.
