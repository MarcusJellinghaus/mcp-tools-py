# Step 2: `scope stdlib` retries after a cached probe failure

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_2.md`), then implement this step only. Step 1 is already committed. Write the tests first and confirm they fail, then add the implementation and the docs. Run pylint, pytest (`extra_args: ["-n", "auto"]`) and mypy until they all pass, run the formatter, and make one commit.

## WHERE

- `tests/test_environment_info.py`, classes `TestResolveScope` and `TestProbeScript`
- `src/mcp_tools_py/utils/target_scripts/probe.py`: `_scope`, `_USAGE`
- `src/mcp_tools_py/utils/environment_info.py`: `resolve_scope`, module docstring
- `docs/architecture/architecture.md`: line 176

## WHAT

No signatures change:

- `_scope(name: str) -> str` also answers `"stdlib"`.
- `resolve_scope(interpreter: str, scope: str) -> ScopeResolution` falls through to the named-scope code when the cached info has an error.

Tests:

```python
# TestResolveScope: replaces test_stdlib_failure_when_probe_untrustworthy
@pytest.mark.parametrize("retry, expected", [...])
def test_stdlib_retries_after_cached_failure(
    self, retry: CommandResult, expected: ScopeResolution
) -> None:

# TestProbeScript
def test_real_child_scope_stdlib_matches_info(self) -> None:
```

`test_stdlib_uses_cached_info_no_subprocess` and `test_failure_is_cached_and_fails_open` stay unchanged and must keep passing.

## HOW

- `probe.py` already imports `sysconfig`. Keep the call inline, with no helper shared with `_info`.
- In `resolve_scope`, do not call `cache_clear` or otherwise touch the cache.
- In `tests/test_environment_info.py`, add `ScopeResolution` to the `environment_info` import and import `CommandResult` from `mcp_tools_py.utils.subprocess_runner`.
- The retry test patches only `mcp_tools_py.utils.environment_info.execute_command`, so it exercises the real cache. The autouse fixture in `tests/conftest.py` clears the cache between tests.
- If `tests/test_environment_info.py` ends up over 750 lines, move `TestResolveScope` to a new `tests/test_resolve_scope.py` rather than allowlisting it.

## ALGORITHM

`_scope`, before `find_spec`:

```
if name == "stdlib":
    return sysconfig.get_paths()["stdlib"]
```

`resolve_scope`:

```
if scope == "stdlib":
    info = get_environment_info(interpreter)
    if not info.error:
        return ScopeResolution(directory=info.stdlib)
run probe.py scope <scope> uncached, exactly as the existing code does
```

`test_stdlib_retries_after_cached_failure`:

```
mock_exec.side_effect = [make_command_result(return_code=1, stderr="info failed"), retry]
assert resolve_scope(interpreter, "stdlib") == expected
assert mock_exec.call_args.args[0][-2:] == ["scope", "stdlib"]
error = get_environment_info(interpreter).error
assert error is not None and "info failed" in error
assert mock_exec.call_count == 2
```

`test_real_child_scope_stdlib_matches_info`:

```
run probe.py info and probe.py scope stdlib under sys.executable, timeout_seconds=60
assert both return codes are 0
assert scope stdout, stripped == json.loads(info stdout)["stdlib"]
```

## DATA

Parametrised cases for the retry test:

| `retry` | `expected` |
|---|---|
| `make_command_result(stdout="/some/stdlib\n")` | `ScopeResolution(directory="/some/stdlib")` |
| `make_command_result(return_code=-1, timed_out=True, execution_error="Process timed out after 30 seconds")` | `ScopeResolution(error=f"resolving scope 'stdlib' timed out after {PROBE_TIMEOUT_SECONDS} seconds")` |
| `make_command_result(return_code=1, stderr="boom")` | `ScopeResolution(error="could not resolve scope 'stdlib': boom")` |

## Docs

- `probe.py` `_USAGE`: change `probe.py scope NAME` to `probe.py scope stdlib|NAME`.
- `probe.py` `_scope` docstring: `name` is `"stdlib"` or a module or package name. `"stdlib"` returns the interpreter's standard library directory.
- `resolve_scope` docstring: `stdlib` is answered from the cached probe. After a cached failure it is probed afresh, leaving the cache untouched. Other names are always probed afresh.
- `environment_info.py` module docstring (lines 8-9): `locate_packages` and `resolve_scope` for named scopes both probe afresh on every call, and `resolve_scope` also probes `stdlib` afresh after a cached failure.
- `docs/architecture/architecture.md:176`: change `scope` (a package's own directory, for `search_library_files`) to `scope` (the directory a `search_library_files` scope names: the standard library for `stdlib`, otherwise a package's own directory).
