# Issue #157: Add finalization step to reinstall_local.bat

## Summary

Add a finalization step to `reinstall_local.bat`, switch to silent-deactivate for venv handling, and update `read_github_deps.py` with `packages-no-deps` support and a path-existence guard.

## Architectural / Design Changes

- **No new modules or packages** — all changes are to existing tooling scripts.
- **`read_github_deps.py`**: Gains a second output mode. Currently emits `uv pip install "pkg"` for `packages` entries. After this change, it also emits `uv pip install --no-deps "pkg"` for `packages-no-deps` entries. Adds a defensive early-return when `pyproject.toml` is missing.
- **`reinstall_local.bat`**: Installation pipeline grows from 6 to 7 steps. A new finalization step (re-install local editable) ensures the local source always takes precedence over GitHub deps that might bundle a copy of the same package. Venv startup guard is simplified from "error out" to "silently deactivate", matching the mcp-coder pattern.

## Files Modified

| File | Change |
|------|--------|
| `tools/read_github_deps.py` | Add `packages-no-deps` support + `path.exists()` guard |
| `tests/test_read_github_deps.py` | New test file for `read_github_deps.py` |
| `tools/reinstall_local.bat` | Silent deactivate + finalization step + renumber 6→7 |

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Update `read_github_deps.py`: add path guard + `packages-no-deps` support (TDD) | Tests + implementation |
| 2 | Update `reinstall_local.bat`: silent deactivate + finalization step + renumber | Script changes only |
