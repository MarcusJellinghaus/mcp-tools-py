# Test Execution Progress Tracker

**Date**: _YYYY-MM-DD_
**Executor**: _name_
**MCP tools-py version**: _version_
**Branch**: _branch name_

---

## Phase 1: Read-Only Tools

### Test 1: `run_pylint_check`

| # | Test | Status | Notes |
|---|------|--------|-------|
| 1a | Default run | ⬜ | |
| 1b | Scoped to directory | ⬜ | |
| 1c | Extra args | ⬜ | |
| 1d | Max issues | ⬜ | |

### Test 2: `run_pytest_check`

| # | Test | Status | Notes |
|---|------|--------|-------|
| 2a | Sample project only | ⬜ | |
| 2b | Single file | ⬜ | |
| 2c | Single test function | ⬜ | |
| 2d | Keyword filter | ⬜ | |
| 2e | With env vars | ⬜ | |

### Test 3: `run_mypy_check`

| # | Test | Status | Notes |
|---|------|--------|-------|
| 3a | Strict mode (default) | ⬜ | |
| 3b | Non-strict | ⬜ | |
| 3c | Disable error codes | ⬜ | |
| 3d | Follow imports: skip | ⬜ | |

### Test 4: `list_symbols`

| # | Test | Status | Notes |
|---|------|--------|-------|
| 4a | Models file | ⬜ | |
| 4b | Utils file | ⬜ | |
| 4c | Services file | ⬜ | |
| 4d | Nonexistent file | ⬜ | |

### Test 5: `find_references`

| # | Test | Status | Notes |
|---|------|--------|-------|
| 5a | Widely-used constant | ⬜ | |
| 5b | Class across modules | ⬜ | |
| 5c | Function with fewer refs | ⬜ | |
| 5d | Nonexistent symbol | ⬜ | |

---

## Phase 2: Dry-Run Mutations

| # | Test | Status | git diff clean? | Notes |
|---|------|--------|-----------------|-------|
| 6a | rename_symbol dry run | ⬜ | ⬜ | |
| 7a | move_symbol dry run | ⬜ | ⬜ | |
| 8a | move_module dry run | ⬜ | ⬜ | |

---

## Phase 3: Apply + Verify + Revert

### Test 6: `rename_symbol`

| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 6b | Apply rename | ⬜ | |
| 6b-v1 | git diff shows expected files | ⬜ | |
| 6b-v2 | Tests pass | ⬜ | |
| 6b-v3 | list_symbols confirms rename | ⬜ | |
| 6c | Teardown (git checkout) | ⬜ | |

### Test 7: `move_symbol`

| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 7b | Apply move | ⬜ | |
| 7b-v1 | git diff shows expected files | ⬜ | |
| 7b-v2 | Source no longer has symbol | ⬜ | |
| 7b-v3 | Dest now has symbol | ⬜ | |
| 7b-v4 | Tests pass | ⬜ | |
| 7c | Teardown (git checkout) | ⬜ | |

### Test 8: `move_module`

| Step | Description | Status | Notes |
|------|-------------|--------|-------|
| 8b | Apply move | ⬜ | |
| 8b-v1 | Original file removed | ⬜ | |
| 8b-v2 | New location exists | ⬜ | |
| 8b-v3 | Imports rewritten | ⬜ | |
| 8b-v4 | Tests pass | ⬜ | |
| 8c | Teardown (git checkout + clean) | ⬜ | |

---

## Legend

- ⬜ Not started
- ✅ Pass
- ❌ Fail
- ⏭️ Skipped
