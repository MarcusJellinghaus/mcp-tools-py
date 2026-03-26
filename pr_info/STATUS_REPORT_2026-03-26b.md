# Manual Test Run Status Report

## Run Info

| Field | Value |
|-------|-------|
| Date | 2026-03-26 |
| Executor | Claude Opus 4.6 |
| MCP tools-py version | current (editable install) |
| Branch | 112-rename_symbol-move_symbol-move_module-all-hang-indefinitely |
| Git SHA | 611e6de27e51e342c7940ba2b07b8c30178c1ec0 |
| Run start | 2026-03-26 07:19:34 |
| Run end | 2026-03-26 07:27:21 |
| Total duration | ~8m |

## Summary

| Phase | Total | Passed | Failed | Skipped | Duration |
|-------|-------|--------|--------|---------|----------|
| Phase 1: Read-only | 21 | 21 | 0 | 0 | ~3m |
| Phase 2: Dry-run | 3 | 3 | 0 | 0 | ~30s |
| Phase 3: Apply+verify | 15 | 15 | 0 | 0 | ~4m |
| **Total** | **39** | **39** | **0** | **0** | **~8m** |

## Per-Tool Results

### run_pylint_check (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 1a | Default run | ✅ | No issues, no crash |
| 1b | Scoped to directory | ✅ | Correctly scoped to sample project |
| 1c | Extra args | ✅ | --disable=C0114 accepted |
| 1d | Max issues | ✅ | max_issues=5 accepted |

### run_pytest_check (5/5 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 2a | Sample project only | ✅ | 11 tests collected, all pass |
| 2b | Single file | ✅ | 4 tests from test_models.py |
| 2c | Single test function | ✅ | 1 test with -vvv |
| 2d | Keyword filter | ✅ | 3 "order" tests filtered correctly |
| 2e | With env vars | ✅ | DEBUG=1 accepted, 11 pass |

### run_mypy_check (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 3a | Strict mode | ✅ | No type errors |
| 3b | Non-strict | ✅ | No type errors |
| 3c | Disable error codes | ✅ | import, no-untyped-def suppressed |
| 3d | Follow imports: skip | ✅ | Parameter accepted |

### list_symbols (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 4a | Models file | ✅ | MAX_NAME_LENGTH, DEFAULT_STATUS, User, Order |
| 4b | Utils file | ✅ | create_user, is_active, format_user |
| 4c | Services file | ✅ | register_user, place_order |
| 4d | Nonexistent file | ✅ | Error: file not found |

### find_references (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 5a | Widely-used constant | ✅ | 10 refs across models, utils, test_models, test_utils |
| 5b | Class across modules | ✅ | 19 refs across all 6 files |
| 5c | Function with fewer refs | ✅ | 3 refs in utils.py, test_utils.py |
| 5d | Nonexistent symbol | ✅ | Error with available symbols listed |

### rename_symbol (5/5 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 6a | Dry run | ✅ | Preview: 4 files, no changes applied |
| 6b | Apply | ✅ | 4 files modified, NAME_MAX_CHARS propagated |
| 6b-v2 | Tests pass | ✅ | 11/11 |
| 6b-v3 | Symbols updated | ✅ | NAME_MAX_CHARS in list, MAX_NAME_LENGTH gone |
| 6c | Teardown | ✅ | Clean recreate |

### move_symbol (6/6 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 7a | Dry run | ✅ | Preview: 3 files, no changes applied |
| 7b | Apply | ✅ | 3 files modified |
| 7b-v2 | Source updated | ✅ | format_user removed from utils.py |
| 7b-v3 | Dest updated | ✅ | format_user added to services.py |
| 7b-v4 | Tests pass | ✅ | 11/11 |
| 7c | Teardown | ✅ | Clean recreate |

### move_module (6/6 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 8a | Dry run | ✅ | Preview: 3 files, no changes applied |
| 8b | Apply | ✅ | 3 files modified, helpers/ package created |
| 8b-v1 | Original removed | ✅ | utils.py gone from original path |
| 8b-v2 | New location | ✅ | helpers/utils.py exists |
| 8b-v3 | Imports rewritten | ✅ | services.py → ...helpers.utils |
| 8b-v4 | Tests pass | ✅ | 11/11 |
| 8c | Teardown | ✅ | Clean delete |

## Issues Found

None. All 39 test steps passed.

## Observations

1. **[OBS] move_module requires git-tracked files**: The first attempt at 8b failed with "utils.py is not tracked by git". This is expected behavior — the tool uses `git mv` internally. Files must be `git add`-ed before `move_module` can operate on them. This was documented in the error message, which is helpful.

2. **[OBS] 2d path warning**: The keyword filter test (2d) produced an informational message "Path 'order' not found relative to project_dir" because `-k order` was passed alongside a path arg and the tool attempted to treat "order" as a path too. This did not affect functionality — 3 tests were correctly filtered and passed.

3. **[OBS] find_references helpful error**: When a nonexistent symbol was requested (5d), the tool returned available symbols as suggestions. Good UX.

## Conclusion

**Overall verdict: PASS**

- **All tools functional?** Yes — all 8 tools (run_pylint_check, run_pytest_check, run_mypy_check, list_symbols, find_references, rename_symbol, move_symbol, move_module) work correctly.
- **Dry-run mode reliable?** Yes — all 3 dry-run tests confirmed no files were modified (verified via git diff).
- **Import rewriting correct?** Yes — rename_symbol propagated across 4 files, move_symbol updated imports in test_utils.py, move_module rewrote imports in services.py and test_utils.py.
- **Tests pass after mutations?** Yes — all 11 sample project tests passed after each mutation (rename, move_symbol, move_module).
- **Clean revert possible?** Yes — delete + recreate from SAMPLE_PROJECT_FILES.md restored clean state each time.
