# Implementation Review Log — Run 1

**Issue:** #176 — chore: complete mcp-coder-utils adoption and add shared libraries docs
**Date:** 2026-04-21

## Round 1 — 2026-04-21

**Findings:**
- All 3 shim files (`log_utils.py`, `utils/subprocess_runner.py`, `utils/file_utils.py`) correctly re-export from `mcp_coder_utils` with `__all__` and `# noqa: F401`
- No remaining direct `mcp_coder_utils` imports in production code (only shim files import directly)
- No remaining direct `mcp_coder_utils` imports in test code (except `test_shim_reexports.py` which intentionally tests identity)
- Import-linter `mcp_coder_utils_isolation` contract structure is correct but missing `include_external_packages = True` in top-level config — without it, grimp doesn't detect external package edges, causing "No matches for ignored import" warnings that fail CI
- CLAUDE.md "Shared libraries" section is accurate and well-placed
- `code_checker_pytest/utils.py` correctly deduped `read_file` via shim import
- `test_shim_reexports.py` provides identity-equality coverage for all 3 shims
- All code quality checks pass: pylint, pytest (472 passed, 1 skipped), mypy

**Decisions:**
- Accept: `.importlinter` needs `include_external_packages = True` and correct ignore paths to pass CI lint-imports step

**Changes:**
- Added `include_external_packages = True` to `[importlinter]` section
- Updated `ignore_imports` to use correct edge names (`-> mcp_coder_utils` for all three shims)

**Status:** Committed

## Final Status

**Rounds:** 1
**Code changes:** `.importlinter` — fixed external package detection config
**All checks pass:** pylint, pytest, mypy, lint-imports
