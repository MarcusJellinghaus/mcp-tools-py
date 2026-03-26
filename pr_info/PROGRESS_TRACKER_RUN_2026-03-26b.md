# Test Execution Progress Tracker

**Date**: 2026-03-26
**Executor**: Claude Opus 4.6
**MCP tools-py version**: current (editable install)
**Branch**: 112-rename_symbol-move_symbol-move_module-all-hang-indefinitely

**Run start**: 2026-03-26 07:19:34
**Run end**: 2026-03-26 07:27:21
**Total duration**: ~8m

---

## Phase 1: Read-Only Tools

### Test 1: `run_pylint_check`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 1a | Default run | ✅ | ~5s | No issues found |
| 1b | Scoped to directory | ✅ | ~5s | Scoped correctly |
| 1c | Extra args | ✅ | ~5s | --disable=C0114 accepted |
| 1d | Max issues | ✅ | ~5s | max_issues=5 accepted |

### Test 2: `run_pytest_check`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 2a | Sample project only | ✅ | ~16s | 11 tests, all pass |
| 2b | Single file | ✅ | ~10s | 4 model tests |
| 2c | Single test function | ✅ | ~11s | 1 test with -vvv |
| 2d | Keyword filter | ✅ | ~11s | 3 "order" tests filtered |
| 2e | With env vars | ✅ | ~16s | DEBUG=1 accepted, 11 pass |

### Test 3: `run_mypy_check`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 3a | Strict mode (default) | ✅ | ~5s | No type errors |
| 3b | Non-strict | ✅ | ~5s | No type errors |
| 3c | Disable error codes | ✅ | ~5s | Codes accepted |
| 3d | Follow imports: skip | ✅ | ~5s | Parameter accepted |

### Test 4: `list_symbols`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 4a | Models file | ✅ | ~2s | MAX_NAME_LENGTH, DEFAULT_STATUS, User, Order |
| 4b | Utils file | ✅ | ~2s | create_user, is_active, format_user |
| 4c | Services file | ✅ | ~2s | register_user, place_order |
| 4d | Nonexistent file | ✅ | ~2s | Error: file not found |

### Test 5: `find_references`

| # | Test | Status | Duration | Notes |
|---|------|--------|----------|-------|
| 5a | Widely-used constant | ✅ | ~3s | 10 refs across 4 files |
| 5b | Class across modules | ✅ | ~3s | 19 refs across 6 files |
| 5c | Function with fewer refs | ✅ | ~3s | 3 refs in 2 files |
| 5d | Nonexistent symbol | ✅ | ~2s | Error with available symbols listed |

---

## Phase 2: Dry-Run Mutations

| # | Test | Status | Duration | git diff clean? | Notes |
|---|------|--------|----------|-----------------|-------|
| 6a | rename_symbol dry run | ✅ | ~3s | ✅ | Preview: 4 files would change |
| 7a | move_symbol dry run | ✅ | ~3s | ✅ | Preview: 3 files would change |
| 8a | move_module dry run | ✅ | ~3s | ✅ | Preview: 3 files would change |

---

## Phase 3: Apply + Verify + Revert

### Test 6: `rename_symbol`

| Step | Description | Status | Duration | Notes |
|------|-------------|--------|----------|-------|
| 6b | Apply rename | ✅ | ~3s | 4 files modified |
| 6b-v1 | Files show expected changes | ✅ | ~2s | utils.py confirmed NAME_MAX_CHARS |
| 6b-v2 | Tests pass | ✅ | ~10s | 11/11 pass |
| 6b-v3 | list_symbols confirms rename | ✅ | ~2s | NAME_MAX_CHARS present, MAX_NAME_LENGTH gone |
| 6c | Teardown (delete + recreate) | ✅ | ~3s | Clean recreate from SAMPLE_PROJECT_FILES.md |

### Test 7: `move_symbol`

| Step | Description | Status | Duration | Notes |
|------|-------------|--------|----------|-------|
| 7b | Apply move | ✅ | ~3s | 3 files modified |
| 7b-v1 | Files show expected changes | ✅ | ~2s | |
| 7b-v2 | Source no longer has symbol | ✅ | ~2s | utils.py: create_user, is_active only |
| 7b-v3 | Dest now has symbol | ✅ | ~2s | services.py: format_user, register_user, place_order |
| 7b-v4 | Tests pass | ✅ | ~12s | 11/11 pass |
| 7c | Teardown (delete + recreate) | ✅ | ~3s | Clean recreate |

### Test 8: `move_module`

| Step | Description | Status | Duration | Notes |
|------|-------------|--------|----------|-------|
| 8b | Apply move | ✅ | ~3s | 3 files modified; [OBS] required git add first |
| 8b-v1 | Original file removed | ✅ | ~1s | utils.py gone from original location |
| 8b-v2 | New location exists | ✅ | ~1s | helpers/utils.py present |
| 8b-v3 | Imports rewritten | ✅ | ~2s | services.py: ...helpers.utils |
| 8b-v4 | Tests pass | ✅ | ~11s | 11/11 pass |
| 8c | Teardown (delete + recreate) | ✅ | ~2s | Clean delete |

---

## Legend

- ⬜ Not started
- ✅ Pass
- ❌ Fail
- ⏭️ Skipped
