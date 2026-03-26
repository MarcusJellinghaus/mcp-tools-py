# Manual Test Status Report — 2026-03-26

## Run Info

| Field | Value |
|-------|-------|
| Date | 2026-03-26 |
| Executor | Claude Opus 4.6 |
| MCP tools-py version | latest |
| Branch | 112-rename_symbol-move_symbol-move_module-all-hang-indefinitely |
| Git SHA | 0a82116 |

## Summary

| Phase | Total | Passed | Failed | Skipped |
|-------|-------|--------|--------|---------|
| Phase 1: Read-Only | 18 | 18 | 0 | 0 |
| Phase 2: Dry-Run | 3 | 3 | 0 | 0 |
| Phase 3: Apply+Verify | 15 | 15 | 0 | 0 |
| **Total** | **36** | **36** | **0** | **0** |

## Per-Tool Results

### `run_pylint_check` (4/4 pass)

| # | Test | Result |
|---|------|--------|
| 1a | Default run | ✅ No issues, no crash |
| 1b | Scoped to directory | ✅ Scoped correctly |
| 1c | Extra args (--disable=C0114) | ✅ Accepted |
| 1d | Max issues=5 | ✅ Accepted |

### `run_pytest_check` (5/5 pass)

| # | Test | Result |
|---|------|--------|
| 2a | Sample project (11 tests) | ✅ All pass |
| 2b | Single file (4 tests) | ✅ All pass |
| 2c | Single test function | ✅ Pass |
| 2d | Keyword filter "order" | ✅ 3 tests filtered correctly |
| 2e | With env vars DEBUG=1 | ✅ All 11 pass |

### `run_mypy_check` (4/4 pass)

| # | Test | Result |
|---|------|--------|
| 3a | Strict mode | ✅ No type errors |
| 3b | Non-strict | ✅ No type errors |
| 3c | Disable error codes | ✅ Accepted |
| 3d | Follow imports: skip | ✅ Accepted |

### `list_symbols` (4/4 pass)

| # | Test | Result |
|---|------|--------|
| 4a | Models file | ✅ All 4 expected symbols found |
| 4b | Utils file | ✅ 3 functions found (+ imports listed) |
| 4c | Services file | ✅ 2 functions found (+ imports listed) |
| 4d | Nonexistent file | ✅ Clear error |

### `find_references` (4/4 pass)

| # | Test | Result |
|---|------|--------|
| 5a | MAX_NAME_LENGTH | ✅ 10 refs across 4 files |
| 5b | User class | ✅ 19 refs across 6 files |
| 5c | format_user | ✅ 3 refs in 2 files |
| 5d | DOES_NOT_EXIST | ✅ Clear error with suggestions |

### `rename_symbol` (5/5 pass)

| # | Test | Result |
|---|------|--------|
| 6a | Dry run | ✅ Preview correct, no files modified |
| 6b | Apply | ✅ 4 files updated correctly |
| 6b-v2 | Tests pass | ✅ 11/11 |
| 6b-v3 | Symbol confirmed | ✅ |
| 6c | Teardown | ✅ Clean state restored |

### `move_symbol` (6/6 pass)

| # | Test | Result |
|---|------|--------|
| 7a | Dry run | ✅ Preview correct, no files modified |
| 7b | Apply | ✅ 3 files updated |
| 7b-v2 | Source clean | ✅ format_user removed |
| 7b-v3 | Dest has symbol | ✅ format_user in services.py |
| 7b-v4 | Tests pass | ✅ 11/11 |
| 7c | Teardown | ✅ Clean state restored |

### `move_module` (6/6 pass)

| # | Test | Result |
|---|------|--------|
| 8a | Dry run | ✅ Preview correct, no files modified |
| 8b | Apply | ✅ Module moved to helpers/ |
| 8b-v1 | Original removed | ✅ |
| 8b-v2 | New location exists | ✅ helpers/utils.py |
| 8b-v3 | Imports rewritten | ✅ ...helpers.utils in services.py and test_utils.py |
| 8b-v4 | Tests pass | ✅ 11/11 |
| 8c | Teardown | ✅ Clean state restored |

## Issues Found

None. All 36 tests passed.

## Observations

1. **[OBS] list_symbols includes imports** (4b, 4c): `list_symbols` reports imported names (e.g., `DEFAULT_STATUS`, `User` in utils.py) alongside locally-defined symbols. The test plan expected only local definitions. This is informational — the tool still shows the expected local symbols, but imports appear as additional entries. Severity: minor/cosmetic.

2. **[OBS] pytest -k warning** (2d): When using `-k "order"` with a path, pytest logs a spurious "Path 'order' not found relative to project_dir" warning. The test still runs correctly with 3 tests filtered. Severity: minor/cosmetic.

3. **[OBS] move_module requires git-tracked files** (8b): `move_module` rejects untracked files with a clear error message directing the user to `git add` first. This is by design (uses `git mv` internally) but worth noting for users who may have just created files. Severity: minor/expected behavior.

## Conclusion

**Overall Verdict: PASS**

| Question | Answer |
|----------|--------|
| All tools functional? | ✅ Yes — all 8 tools work correctly |
| Dry-run mode reliable? | ✅ Yes — no files modified in any dry-run test |
| Import rewriting correct? | ✅ Yes — rename_symbol, move_symbol, and move_module all rewrote imports correctly across the entire project |
| Tests pass after mutations? | ✅ Yes — all 11 sample tests passed after every mutation |
| Clean revert possible? | ✅ Yes — delete+recreate from SAMPLE_PROJECT_FILES.md restored clean state every time |
