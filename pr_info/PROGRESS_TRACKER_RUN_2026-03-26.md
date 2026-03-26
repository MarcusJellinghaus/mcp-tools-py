# Test Execution Progress Tracker

**Date**: 2026-03-26
**Executor**: Claude Opus 4.6
**MCP tools-py version**: latest
**Branch**: 112-rename_symbol-move_symbol-move_module-all-hang-indefinitely
**Git SHA**: 0a82116

**Run start**: 2026-03-26
**Run end**: 2026-03-26
**Total duration**: ~10 min

---

## Phase 1: Read-Only Tools

### Test 1: `run_pylint_check`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 1a | Default run | ✅ | ~5s | No issues found |
| 1b | Scoped to directory | ✅ | ~5s | No issues found, scoped correctly |
| 1c | Extra args | ✅ | ~5s | --disable=C0114 accepted |
| 1d | Max issues | ✅ | ~5s | max_issues=5 accepted |

### Test 2: `run_pytest_check`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 2a | Sample project only | ✅ | 11.5s | 11 tests collected and passed |
| 2b | Single file | ✅ | 11.4s | 4 model tests only |
| 2c | Single test function | ✅ | 10.8s | 1 test with -vvv |
| 2d | Keyword filter | ✅ | 11.0s | 3 "order" tests filtered. [OBS] Spurious "Path 'order' not found" warning logged but tests ran correctly |
| 2e | With env vars | ✅ | 15.1s | 11 tests with DEBUG=1, all pass |

### Test 3: `run_mypy_check`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 3a | Strict mode (default) | ✅ | ~10s | No type errors |
| 3b | Non-strict | ✅ | ~10s | No type errors |
| 3c | Disable error codes | ✅ | ~10s | disable_error_codes accepted |
| 3d | Follow imports: skip | ✅ | ~10s | follow_imports=skip accepted |

### Test 4: `list_symbols`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 4a | Models file | ✅ | ~2s | MAX_NAME_LENGTH, DEFAULT_STATUS, User, Order — all 4 expected |
| 4b | Utils file | ✅ | ~2s | create_user, is_active, format_user present. [OBS] Also lists imports as symbols (DEFAULT_STATUS, MAX_NAME_LENGTH, User) |
| 4c | Services file | ✅ | ~2s | register_user, place_order present. [OBS] Also lists imports (Order, User, create_user, is_active) |
| 4d | Nonexistent file | ✅ | ~1s | Error: "file not found" |

### Test 5: `find_references`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 5a | Widely-used constant | ✅ | ~3s | 10 refs across models.py, utils.py, test_models.py, test_utils.py |
| 5b | Class across modules | ✅ | ~3s | 19 refs across all 6 expected files |
| 5c | Function with fewer refs | ✅ | ~3s | 3 refs in utils.py and test_utils.py |
| 5d | Nonexistent symbol | ✅ | ~1s | Clear error with available symbols listed |

---

## Phase 2: Dry-Run Mutations

| # | Test | Status | Duration | git diff clean? | Notes |
|---|------|--------|----------|-----------------|-------|
| 6a | rename_symbol dry run | ✅ | ~3s | ✅ | Preview shows 4 files, files unchanged |
| 7a | move_symbol dry run | ✅ | ~3s | ✅ | Preview shows 3 files, files unchanged |
| 8a | move_module dry run | ✅ | ~3s | ✅ | Preview shows 3 files, files unchanged |

---

## Phase 3: Apply + Verify + Revert

### Test 6: `rename_symbol`

| Step | Description | Status | Duration | Notes |
|------|-------------|--------|----------|-------|
| 6b | Apply rename | ✅ | ~5s | 4 files modified as expected |
| 6b-v1 | Files show NAME_MAX_CHARS | ✅ | ~2s | models.py confirmed |
| 6b-v2 | Tests pass | ✅ | 10.7s | 11/11 pass |
| 6b-v3 | list_symbols confirms rename | ✅ | ~2s | NAME_MAX_CHARS shown, MAX_NAME_LENGTH gone |
| 6c | Teardown (delete + recreate) | ✅ | ~5s | Clean state verified, 11 tests pass |

### Test 7: `move_symbol`

| Step | Description | Status | Duration | Notes |
|------|-------------|--------|----------|-------|
| 7b | Apply move | ✅ | ~5s | 3 files modified |
| 7b-v1 | Files show expected changes | ✅ | ~2s | |
| 7b-v2 | Source no longer has symbol | ✅ | ~2s | format_user gone from utils.py |
| 7b-v3 | Dest now has symbol | ✅ | ~2s | format_user in services.py |
| 7b-v4 | Tests pass | ✅ | 10.9s | 11/11 pass |
| 7c | Teardown (delete + recreate) | ✅ | ~5s | |

### Test 8: `move_module`

| Step | Description | Status | Duration | Notes |
|------|-------------|--------|----------|-------|
| 8b | Apply move | ✅ | ~5s | [OBS] Required git add first — untracked files rejected with clear error message |
| 8b-v1 | Original file removed | ✅ | ~1s | utils.py gone from original location |
| 8b-v2 | New location exists | ✅ | ~1s | helpers/utils.py exists |
| 8b-v3 | Imports rewritten | ✅ | ~2s | services.py and test_utils.py use ...helpers.utils |
| 8b-v4 | Tests pass | ✅ | 15.7s | 11/11 pass |
| 8c | Teardown (delete + recreate) | ✅ | ~5s | git checkout restored clean state |

---

## Legend

- ⬜ Not started
- ✅ Pass
- ❌ Fail
- ⏭️ Skipped
