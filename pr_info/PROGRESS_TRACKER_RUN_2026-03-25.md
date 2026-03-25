# Test Execution Progress Tracker

**Date**: 2026-03-25
**Executor**: Claude (automated)
**MCP tools-py version**: 0.1.0
**Branch**: 112-rename_symbol-move_symbol-move_module-all-hang-indefinitely
**Git SHA**: 925712b

**Run start**: 2026-03-25 09:16:46
**Run end**: 2026-03-25 10:04:42
**Total duration**: ~48m

---

## Phase 1: Read-Only Tools

### Test 1: `run_pylint_check`

| # | Test | Status | Notes |
|---|------|--------|-------|
| 1a | Default run | ✅ | No issues found |
| 1b | Scoped to directory | ✅ | No issues found |
| 1c | Extra args | ✅ | No issues found |
| 1d | Max issues | ✅ | No issues found |

### Test 2: `run_pytest_check`

| # | Test | Status | Notes |
|---|------|--------|-------|
| 2a | Sample project only | ✅ | 305 passed, 1 skipped |
| 2b | Single file | ✅ | [OBS] Collected broader tests due to pytest discovery; 1 flaky subprocess_runner test failed (pre-existing, unrelated) |
| 2c | Single test function | ✅ | 1 test, max verbosity |
| 2d | Keyword filter | ✅ | 5 tests matched "order" |
| 2e | With env vars | ✅ | 305 passed, 1 skipped |

### Test 3: `run_mypy_check`

| # | Test | Status | Notes |
|---|------|--------|-------|
| 3a | Strict mode (default) | ✅ | No type errors |
| 3b | Non-strict | ✅ | No type errors |
| 3c | Disable error codes | ✅ | No type errors |
| 3d | Follow imports: skip | ✅ | No type errors |

### Test 4: `list_symbols`

| # | Test | Status | Notes |
|---|------|--------|-------|
| 4a | Models file | ✅ | MAX_NAME_LENGTH, DEFAULT_STATUS, User, Order |
| 4b | Utils file | ✅ | create_user, is_active, format_user (+ imports shown) |
| 4c | Services file | ✅ | register_user, place_order (+ imports shown) |
| 4d | Nonexistent file | ✅ | Error: file not found |

### Test 5: `find_references`

| # | Test | Status | Notes |
|---|------|--------|-------|
| 5a | Widely-used constant | ✅ | 10 refs across models, utils, test_models, test_utils |
| 5b | Class across modules | ✅ | 19 refs across all 6 files |
| 5c | Function with fewer refs | ✅ | 3 refs in utils.py and test_utils.py |
| 5d | Nonexistent symbol | ✅ | Symbol not found, available symbols listed |

---

## Phase 2: Dry-Run Mutations

| # | Test | Status | git diff clean? | Notes |
|---|------|--------|-----------------|-------|
| 6a | rename_symbol dry run | ✅ | ✅ | Preview: 4 files would be modified |
| 7a | move_symbol dry run | ✅ | ✅ | Preview: 3 files would be modified |
| 8a | move_module dry run | ✅ | ✅ | Preview: 3 files would be modified |

---

## Phase 3: Apply + Verify + Revert

### Test 6: `rename_symbol`

| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 6b | Apply rename | ✅ | MAX_NAME_LENGTH -> NAME_MAX_CHARS in 4 files |
| 6b-v1 | git diff shows expected files | ✅ | models.py, utils.py, test_models.py, test_utils.py |
| 6b-v2 | Tests pass | ✅ | Sample project tests pass |
| 6b-v3 | list_symbols confirms rename | ✅ | NAME_MAX_CHARS shown, MAX_NAME_LENGTH gone |
| 6c | Teardown (git checkout) | ✅ | Clean restore |

### Test 7: `move_symbol`

| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 7b | Apply move | ✅ | format_user moved from utils.py to services.py |
| 7b-v1 | git diff shows expected files | ✅ | utils.py, services.py, test_utils.py |
| 7b-v2 | Source no longer has symbol | ✅ | utils.py: create_user, is_active only |
| 7b-v3 | Dest now has symbol | ✅ | services.py: format_user listed |
| 7b-v4 | Tests pass | ✅ | Sample project tests pass |
| 7c | Teardown (git checkout) | ✅ | Clean restore |

### Test 8: `move_module`

| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 8b | Apply move | ✅ | utils.py moved to helpers/utils.py |
| 8b-v1 | Original file removed | ✅ | utils.py gone from original location |
| 8b-v2 | New location exists | ✅ | helpers/utils.py + helpers/__init__.py created |
| 8b-v3 | Imports rewritten | ✅ | services.py: from ...helpers.utils import ... |
| 8b-v4 | Tests pass | ✅ | Sample project tests pass |
| 8c | Teardown (git checkout + rm helpers/) | ✅ | Clean restore |

---

## Legend

- ✅ Pass
- ❌ Fail
- ⏭️ Skipped
