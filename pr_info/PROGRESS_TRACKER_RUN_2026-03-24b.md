# Test Execution Progress Tracker

**Date**: 2026-03-24
**Executor**: Claude (automated)
**MCP tools-py version**: current (branch build)
**Branch**: 112-rename_symbol-move_symbol-move_module-all-hang-indefinitely

**Run start**: 2026-03-24 23:36:32
**Run end**: 2026-03-24 23:53:12
**Total duration**: 16m 40s

---

## Phase 1: Read-Only Tools

### Test 1: `run_pylint_check`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 1a | Default run | ✅ | ~10s | No issues found |
| 1b | Scoped to directory | ✅ | ~10s | No issues found |
| 1c | Extra args | ✅ | ~10s | No issues found (--disable=C0114) |
| 1d | Max issues | ✅ | ~10s | No issues found (max_issues=5) |

### Test 2: `run_pytest_check`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 2a | Sample project only | ✅ | 49.45s | [OBS] Collected 302 tests (all project tests), not just 11 sample tests. Path filter in extra_args does not limit test collection. |
| 2b | Single file | ✅ | 65.67s | [OBS] Collected 302 tests, not just 4. Same path filter issue as 2a. |
| 2c | Single test function | ✅ | 118.44s | [OBS] Collected 302 tests, not just 1. Same path filter issue. |
| 2d | Keyword filter | ✅ | 22.80s | Collected 5 tests with -k "order". Keyword filter works correctly. |
| 2e | With env vars | ✅ | 109.49s | [OBS] Collected 302 tests. env_vars parameter accepted without error. Same path filter issue as 2a. |

### Test 3: `run_mypy_check`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 3a | Strict mode (default) | ✅ | ~15s | No type errors found |
| 3b | Non-strict | ✅ | ~15s | No type errors found |
| 3c | Disable error codes | ✅ | ~15s | No type errors found |
| 3d | Follow imports: skip | ✅ | ~15s | No type errors found |

### Test 4: `list_symbols`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 4a | Models file | ✅ | <1s | Found: MAX_NAME_LENGTH, DEFAULT_STATUS, User, Order |
| 4b | Utils file | ✅ | <1s | [OBS] Also shows imported symbols (DEFAULT_STATUS, MAX_NAME_LENGTH, User) alongside own functions (create_user, is_active, format_user) |
| 4c | Services file | ✅ | <1s | [OBS] Also shows imported symbols (Order, User, create_user, is_active) alongside own functions (register_user, place_order) |
| 4d | Nonexistent file | ✅ | <1s | Error: file not found (correct) |

### Test 5: `find_references`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 5a | Widely-used constant | ✅ | <1s | 10 refs in models.py, utils.py, test_models.py, test_utils.py |
| 5b | Class across modules | ✅ | <1s | 19 refs across all 6 expected files |
| 5c | Function with fewer refs | ✅ | <1s | 3 refs in utils.py and test_utils.py |
| 5d | Nonexistent symbol | ✅ | <1s | Error with available symbols listed (correct) |

---

## Phase 2: Dry-Run Mutations

| # | Test | Status | Duration | git diff clean? | Notes |
|---|------|--------|----------|-----------------|-------|
| 6a | rename_symbol dry run | ❌ | 120s | ✅ | Timed out after 120s |
| 7a | move_symbol dry run | ❌ | 120s | ✅ | Timed out after 120s |
| 8a | move_module dry run | ❌ | 120s | ✅ | Timed out after 120s |

---

## Phase 3: Apply + Verify + Revert

### Test 6: `rename_symbol`

| Step | Description | Status | Duration | Notes |
|------|-------------|--------|----------|-------|
| 6b | Apply rename | ⏭️ | | Skipped — dry run timed out |
| 6b-v1 | git diff shows expected files | ⏭️ | | |
| 6b-v2 | Tests pass | ⏭️ | | |
| 6b-v3 | list_symbols confirms rename | ⏭️ | | |
| 6c | Teardown (delete + recreate) | ⏭️ | | |

### Test 7: `move_symbol`

| Step | Description | Status | Duration | Notes |
|------|-------------|--------|----------|-------|
| 7b | Apply move | ⏭️ | | Skipped — dry run timed out |
| 7b-v1 | git diff shows expected files | ⏭️ | | |
| 7b-v2 | Source no longer has symbol | ⏭️ | | |
| 7b-v3 | Dest now has symbol | ⏭️ | | |
| 7b-v4 | Tests pass | ⏭️ | | |
| 7c | Teardown (delete + recreate) | ⏭️ | | |

### Test 8: `move_module`

| Step | Description | Status | Duration | Notes |
|------|-------------|--------|----------|-------|
| 8b | Apply move | ⏭️ | | Skipped — dry run timed out |
| 8b-v1 | Original file removed | ⏭️ | | |
| 8b-v2 | New location exists | ⏭️ | | |
| 8b-v3 | Imports rewritten | ⏭️ | | |
| 8b-v4 | Tests pass | ⏭️ | | |
| 8c | Teardown (delete + recreate) | ⏭️ | | |

---

## Legend

- ⬜ Not started
- ✅ Pass
- ❌ Fail
- ⏭️ Skipped
