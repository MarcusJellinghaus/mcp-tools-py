# Step 2 — environment_info.py: EnvironmentInfo.stdlib + resolve_scope()

Part of the plan in `pr_info/steps/summary.md` (issue #228). Read that file first.

## Precondition

Step 1 is committed: `probe.py` has the `stdlib` info field and the `scope`
subcommand. If `probe.py scope` does not exist yet, write one line to
`pr_info/.blocked.txt` and stop.

## WHERE

- `src/mcp_tools_py/utils/environment_info.py` (implementation)
- `tests/test_environment_info.py`, new `TestResolveScope` class (tests)

## WHAT

- `EnvironmentInfo`: add a field `stdlib: str = ""`, placed with the other
  probe-blob fields (before `error`). Defaulted so every existing
  `EnvironmentInfo(...)` / `make_environment_info()` call site in the test suite
  keeps working untouched.
- In `get_environment_info`, when parsing a successful probe blob, read
  `stdlib=blob.get("stdlib", "")` (`.get`, not `[...]`, so a blob without the key —
  e.g. the existing hand-written `_BLOB` fixture — still parses).
- New frozen dataclass `ScopeResolution`: `directory: Optional[str] = None`,
  `error: Optional[str] = None` — exactly one is set.
- New function `resolve_scope(interpreter: str, scope: str) -> ScopeResolution`.

## HOW

`resolve_scope` lives next to `locate_packages` (same "ask the probe about the
target interpreter" family) but stays much smaller: it has no PYTHONPATH-safety
classification to do, since it only ever needs to answer with one directory.
`scope == "stdlib"` is answered from the already-cached `get_environment_info`
result — no subprocess. Anything else runs `probe.py scope NAME` uncached via
`execute_command`, same timeout/`PROBE_TIMEOUT_SECONDS`/`STDERR_SNIPPET` constants
already defined in this module.

## ALGORITHM (`resolve_scope`)

```
if scope == "stdlib":
    info = get_environment_info(interpreter)
    return error(info.error) if info.error else directory(info.stdlib)
run [interpreter, probe_script_path(), "scope", scope], timeout_seconds=PROBE_TIMEOUT_SECONDS
if timed_out: return error("resolving scope '<scope>' timed out after N seconds")
if execution_error or return_code != 0: return error("could not resolve scope '<scope>': <detail>")
return directory(stdout.strip())
```

## DATA

`ScopeResolution(directory=<abs path str>, error=None)` on success, or
`ScopeResolution(directory=None, error=<message str>)` on failure. The message
names the scope and, for subprocess failures, the interpreter/stderr snippet —
same style as `locate_packages`'s existing error strings.

## Tests (write first, see them fail, then implement)

`TestResolveScope` in `tests/test_environment_info.py`, mocking
`mcp_tools_py.utils.environment_info.execute_command` (and, for the stdlib cases,
patching `get_environment_info` directly — use a unique interpreter string per test
to avoid the `lru_cache` from a previous test, as the existing tests in this file
already do):

- `test_stdlib_uses_cached_info_no_subprocess`: patch `get_environment_info` to
  return a successful `EnvironmentInfo(..., stdlib="/some/stdlib")`; call
  `resolve_scope(interpreter, "stdlib")`; assert `.directory == "/some/stdlib"` and
  `execute_command` was never called.
- `test_stdlib_failure_when_probe_untrustworthy`: patch `get_environment_info` to
  return `EnvironmentInfo(..., error="boom")`; assert `.error` is set and mentions
  `"boom"`; `execute_command` not called.
- `test_package_scope_runs_the_scope_subcommand`: mock `execute_command` returning
  `stdout="/some/dir\n"`; assert `resolve_scope(interpreter, "mypy").directory ==
  "/some/dir"`; assert the command list passed is
  `[interpreter, str(probe_script_path()), "scope", "mypy"]`.
- `test_timeout_is_reported`: mock a `timed_out` result; assert `.error` contains
  `"timed out"` and `"mypy"`.
- `test_nonzero_exit_is_reported`: mock `return_code=1, stderr="no module"`; assert
  `.error` contains `"no module"`.
- One real-subprocess check (no mocking), alongside the existing
  `TestProbeScript`/`TestLocatePackages` real-child tests: resolve `scope="json"`
  under `sys.executable` and assert the returned directory contains
  `__init__.py`.

## Commit

One commit: `feat(environment_info): add stdlib field and resolve_scope()`

## LLM prompt

> Read `pr_info/steps/summary.md` for context, then implement
> `pr_info/steps/step_2.md` only. Write the `TestResolveScope` tests described under
> "Tests" first, confirm they fail (missing `resolve_scope`/`ScopeResolution`), then
> add `EnvironmentInfo.stdlib`, `ScopeResolution` and `resolve_scope` to
> `src/mcp_tools_py/utils/environment_info.py` exactly as specified under WHAT/HOW/
> ALGORITHM/DATA. Re-run the tests until they pass, and confirm no other existing
> test in the file broke (the `stdlib` field must not require changes to the
> existing `_BLOB` fixture or `make_environment_info`). Run
> `mcp__mcp-tools-py__run_pylint_check`, `mcp__mcp-tools-py__run_pytest_check`
> (`extra_args=["-n", "auto", "-m", "not integration"]`) and
> `mcp__mcp-tools-py__run_mypy_check` — all must pass. Then run
> `mcp__mcp-tools-py__run_format_code`, stage the changes, and create exactly one
> commit: `feat(environment_info): add stdlib field and resolve_scope()`. If the
> precondition above does not hold, write one line to `pr_info/.blocked.txt` and stop
> instead.
