# Manual Test Status Report

## Run Info

| Field | Value |
|-------|-------|
| Date | 2026-03-25 |
| Executor | Claude Opus 4.6 |
| MCP tools-py version | dev |
| Branch | 112-rename_symbol-move_symbol-move_module-all-hang-indefinitely |
| Git SHA | baabbc4 |
| Run start | 2026-03-25 20:12:23 |
| Run end | 2026-03-25 20:36:44 |
| Total duration | 24m 21s |

## Summary

| Phase | Total | Passed | Failed | Skipped | Duration |
|-------|-------|--------|--------|---------|----------|
| Phase 1: Read-Only | 17 | 17 | 0 | 0 | ~5m |
| Phase 2: Dry-Run | 3 | 2 | 1 | 0 | ~35s |
| Phase 3: Apply+Verify | 14 | 10 | 4 | 0 | ~3m |
| **Total** | **34** | **29** | **5** | **0** | **24m 21s** |

## Per-Tool Results

### run_pylint_check (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 1a | Default run | ✅ | No issues, no crash |
| 1b | Scoped to directory | ✅ | Correctly scoped |
| 1c | Extra args | ✅ | --disable=C0114 accepted |
| 1d | Max issues | ✅ | max_issues=5 accepted |

### run_pytest_check (5/5 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 2a | Sample project only | ✅ | 11 tests, all pass |
| 2b | Single file | ✅ | 4 tests |
| 2c | Single test function | ✅ | 1 test, -vvv |
| 2d | Keyword filter | ✅ | 3 tests with "order" |
| 2e | With env vars | ✅ | DEBUG=1, 11 pass |

### run_mypy_check (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 3a | Strict mode | ✅ | No errors |
| 3b | Non-strict | ✅ | No errors |
| 3c | Disable error codes | ✅ | Codes suppressed |
| 3d | Follow imports: skip | ✅ | No errors |

### list_symbols (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 4a | Models file | ✅ | All 4 symbols found |
| 4b | Utils file | ✅ | 3 functions found (+ imports) |
| 4c | Services file | ✅ | 2 functions found (+ imports) |
| 4d | Nonexistent file | ✅ | Error message |

### find_references (4/4 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 5a | Widely-used constant | ✅ | 10 refs across 4 files |
| 5b | Class across modules | ✅ | 19 refs across 6 files |
| 5c | Function with fewer refs | ✅ | 3 refs across 2 files |
| 5d | Nonexistent symbol | ✅ | Error with available symbols |

### rename_symbol (5/5 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 6a | Dry run | ✅ | Preview correct, no files modified |
| 6b | Apply | ✅ | All occurrences renamed across 4 files |
| 6b-v2 | Tests pass | ✅ | 11/11 |
| 6b-v3 | Symbols confirm | ✅ | NAME_MAX_CHARS in list |
| 6c | Teardown | ✅ | Clean restore |

### move_symbol (6/6 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 7a | Dry run | ✅ | Preview correct, no files modified |
| 7b | Apply | ✅ | Symbol moved, imports rewritten |
| 7b-v2 | Source cleared | ✅ | format_user removed from utils |
| 7b-v3 | Dest has symbol | ✅ | format_user in services |
| 7b-v4 | Tests pass | ✅ | 11/11 |
| 7c | Teardown | ✅ | Clean restore |

### move_module (1/6 pass)

| # | Test | Result | Details |
|---|------|--------|---------|
| 8a | Dry run | ❌ | Error: dest package not found (should auto-create or at least preview) |
| 8b | Apply | ❌ | Imports rewritten but file NOT moved |
| 8b-v1 | Original removed | ❌ | Still exists |
| 8b-v2 | New location | ❌ | Does not exist |
| 8b-v3 | Imports rewritten | ✅ | Correctly updated |
| 8b-v4 | Tests pass | ❌ | 4/11 — missing module |

## Issues Found

| # | Severity | Tool | Description |
|---|----------|------|-------------|
| 1 | **Blocker** | move_module | Does not auto-create destination package. Dry run errors with "destination package not found" instead of previewing. |
| 2 | **Blocker** | move_module | After manual package creation, imports are rewritten but the source file is NOT physically moved to the destination. Results in broken imports and test failures (4/11 tests). |

## Observations

| # | Tool | Observation |
|---|------|-------------|
| 1 | run_pytest_check | When using `-k` filter, the keyword (e.g. "order") triggers a spurious "Path 'order' not found" warning from path detection logic. Functionally correct but confusing output. |
| 2 | list_symbols | Lists imported symbols alongside locally-defined symbols. Imports show as `instance` or `class` type. Could be confusing — users may expect only locally-defined symbols. |
| 3 | find_references | Import references show as `class` type even for non-class symbols (e.g. `instance MAX_NAME_LENGTH` shown as reference type in test files). Minor labeling issue. |
| 4 | All refactoring tools | No timeout issues — rename_symbol, move_symbol completed in ~9-10s. The original issue (#112) about hanging indefinitely appears resolved. |

## Conclusion

**Overall Verdict: FAIL**

| Question | Answer |
|----------|--------|
| All tools functional? | **No** — move_module has 2 blocker bugs (no auto-create, no file move) |
| Dry-run mode reliable? | **Partially** — rename_symbol and move_symbol dry runs are reliable. move_module dry run errors instead of previewing. |
| Import rewriting correct? | **Yes** — all 3 refactoring tools correctly rewrite imports when they operate |
| Tests pass after mutations? | **Yes** for rename_symbol and move_symbol. **No** for move_module (broken imports). |
| Clean revert possible? | **Yes** — delete + recreate from SAMPLE_PROJECT_FILES.md works reliably |

### Key Findings

- **rename_symbol**: Fully functional. Dry run previews correctly, apply renames across all files, tests pass.
- **move_symbol**: Fully functional. Dry run previews correctly, apply moves symbol and rewrites imports, tests pass.
- **move_module**: Two blocker bugs prevent use. Import rewriting works but file is not physically moved.
- **No hanging**: All refactoring tools completed within 10-18 seconds. The original issue about indefinite hangs appears to be resolved.
