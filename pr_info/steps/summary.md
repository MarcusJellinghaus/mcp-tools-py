# Summary: stdlib scope recovers from a cached probe failure (#218)

## Problem

`get_environment_info` caches failures for the server's lifetime, and `resolve_scope` answers `stdlib` only from that cached result. One failed `info` probe therefore breaks `search_library_files(scope="stdlib")` until restart, and the error reads like a current timeout.

## Goal

While a failure is cached, `scope="stdlib"` retries with an uncached probe. The cached failure stays in place, so no other tool sees a change.

## Architectural / design changes

| Area | Before | After |
|---|---|---|
| `probe.py scope` | Looks up every name as a module | `stdlib` is answered from `sysconfig.get_paths()["stdlib"]`, the same source as `info`; other names are unchanged |
| `resolve_scope("stdlib")`, cached success | Returns `info.stdlib`, no subprocess | Unchanged |
| `resolve_scope("stdlib")`, cached failure | Returns the cached error | Falls through to the existing named-scope code, which runs `probe.py scope stdlib` uncached |
| `search_library_files` handler | Searches whatever path it was given; a missing path gives an empty success and `""` searches the server's working directory | Returns `{"error": ...}` when the resolved path is not a directory, for all scopes |

Design rules from the issue:

- **Failed probes stay cached.** The retry never touches the `lru_cache`, so a search cannot reset what other tools see.
- **A retry's success is not remembered.** While the failure is cached, each stdlib search spawns a subprocess. This cost is accepted.
- **The guard lives in the handler**, not in `resolve_scope`, whose tests use mock paths.
- **Use `os.path.isdir`**, not `Path(...).is_dir()`: `Path("").is_dir()` is True.
- **`probe.py` stays standard library only.** `sysconfig` is already imported, and the call stays inline in `_info` and `_scope` with no helper.

## Files to modify

No files or folders are created by the implementation.

```
src/mcp_tools_py/
  library_search.py                     guard in search_library_files (step 1)
  utils/
    environment_info.py                 resolve_scope fall-through, docstrings (step 2)
    target_scripts/probe.py             _scope answers stdlib, _USAGE, docstring (step 2)
docs/architecture/architecture.md       line 176, scope description (step 2)
tests/
  test_library_search.py                handler test (step 1)
  test_environment_info.py              retry test, real-child test (step 2)
```

## Steps

1. [Step 1](./step_1.md): the handler rejects a resolved path that is not a directory. This stands on its own, because named scopes have the defect today.
2. [Step 2](./step_2.md): `scope stdlib` retries after a cached failure. It relies on the guard from step 1 to report stdout noise as an error.

## Out of scope

- `is_tool_available` logging a warning on every call while the failure is cached.
- `run_pytest_check(coverage=True)` skipping its `pytest-cov` pre-check while the failure is cached.
- Any change to `lru_cache` or to how failures are cached.
