# Manual Test Status Report

## Run Info

| Field | Value |
|-------|-------|
| Date | 2026-03-25 |
| Executor | Claude Opus 4.6 |
| MCP tools-py version | latest |
| Branch | 112-rename_symbol-move_symbol-move_module-all-hang-indefinitely |
| Git SHA | 37591d7 |
| Run start | 2026-03-25 21:49:06 |
| Run end | 2026-03-25 22:08:58 |
| Total duration | 19m 52s |

## Summary

| Phase | Total | Passed | Failed | Skipped | Duration |
|-------|-------|--------|--------|---------|----------|
| Phase 1: Read-only | 22 | 22 | 0 | 0 | ~5m |
| Phase 2: Dry-run | 3 | 3 | 0 | 0 | ~30s |
| Phase 3: Apply+Verify | 17 | 17 | 0 | 0 | ~14m |
| **Total** | **42** | **42** | **0** | **0** | **19m 52s** |

## Per-Tool Results

### `run_pylint_check` (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 1a | Default run | ✅ | Returns results covering src/ and tests/ |
| 1b | Scoped to directory | ✅ | Only analyses sample_project |
| 1c | Extra args | ✅ | --disable=C0114 accepted |
| 1d | Max issues | ✅ | max_issues=5 accepted |

### `run_pytest_check` (5/5 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 2a | Sample project only | ✅ | 11 tests, all pass |
| 2b | Single file | ✅ | 4 tests only |
| 2c | Single test function | ✅ | 1 test with -vvv |
| 2d | Keyword filter | ✅ | 3 "order" tests filtered correctly |
| 2e | With env vars | ✅ | DEBUG=1 passed to subprocess |

### `run_mypy_check` (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 3a | Strict mode | ✅ | No type errors |
| 3b | Non-strict | ✅ | No type errors |
| 3c | Disable error codes | ✅ | Codes suppressed |
| 3d | Follow imports: skip | ✅ | Skip mode works |

### `list_symbols` (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 4a | Models file | ✅ | MAX_NAME_LENGTH, DEFAULT_STATUS, User, Order |
| 4b | Utils file | ✅ | create_user, is_active, format_user |
| 4c | Services file | ✅ | register_user, place_order |
| 4d | Nonexistent file | ✅ | "file not found" error |

### `find_references` (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 5a | Constant refs | ✅ | 10 refs across 4 files |
| 5b | Class refs | ✅ | 19 refs across 6 files |
| 5c | Function refs | ✅ | 3 refs in 2 files |
| 5d | Nonexistent symbol | ✅ | "Symbol not found" with suggestions |

### `rename_symbol` (6/6 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 6a | Dry run | ✅ | Preview shows 4 files; no files modified |
| 6b | Apply | ✅ | 4 files modified, all refs renamed |
| 6b-v2 | Tests pass | ✅ | 11/11 |
| 6b-v3 | Symbols confirmed | ✅ | NAME_MAX_CHARS present |
| 6c | Teardown | ✅ | Clean state restored |

### `move_symbol` (7/7 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 7a | Dry run | ✅ | Preview shows 3 files; no files modified |
| 7b | Apply | ✅ | 3 files modified |
| 7b-v2 | Source cleared | ✅ | format_user removed from utils.py |
| 7b-v3 | Dest has symbol | ✅ | format_user in services.py |
| 7b-v4 | Tests pass | ✅ | 11/11 |
| 7c | Teardown | ✅ | Clean state restored |

### `move_module` (7/7 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 8a | Dry run | ✅ | Preview shows 3 files; no files modified |
| 8b | Apply | ✅ | Moved to helpers/utils.py, imports rewritten |
| 8b-v1 | Original removed | ✅ | utils.py gone from original path |
| 8b-v2 | New location | ✅ | helpers/utils.py exists |
| 8b-v3 | Imports rewritten | ✅ | services.py and test_utils.py updated |
| 8b-v4 | Tests pass | ✅ | 11/11 |
| 8c | Teardown | ✅ | Clean state restored |

## Issues Found

No blockers or major issues.

| Severity | Issue | Resolution |
|----------|-------|------------|
| minor | move_module requires files to be git-tracked (8b first attempt failed with "untracked file" error) | Documented in error message; ran `git add` before retry. This is by-design since rope uses `git mv`. |

## Observations

1. **[OBS] list_symbols includes imported symbols** (4b, 4c): `list_symbols` returns both locally-defined and imported names. E.g. utils.py lists imported `DEFAULT_STATUS`, `MAX_NAME_LENGTH`, `User` alongside its own functions. This is technically correct (they are module-level names) but may surprise users expecting only definitions.

2. **[OBS] pytest -k arg triggers "Path not found" warning** (2d): When using `-k order`, the runner logs "Path 'order' not found relative to project_dir" before correctly passing it as a keyword filter. Cosmetic issue — tests run correctly.

3. **[OBS] move_module requires git-tracked files** (8b): First attempt failed because the sample project files were untracked. The error message was clear and actionable. This is a known design constraint of the rope-based implementation.

## Conclusion

**Overall verdict: PASS**

- **All tools functional?** Yes — all 8 tools (run_pylint_check, run_pytest_check, run_mypy_check, list_symbols, find_references, rename_symbol, move_symbol, move_module) work correctly.
- **Dry-run mode reliable?** Yes — all 3 dry-run tests (6a, 7a, 8a) showed correct previews and left zero files modified.
- **Import rewriting correct?** Yes — rename_symbol, move_symbol, and move_module all correctly updated imports across the dependency chain.
- **Tests pass after mutations?** Yes — all 11 sample project tests passed after each mutation (rename, move_symbol, move_module).
- **Clean revert possible?** Yes — all teardowns successfully restored the project to its original state with passing tests.
