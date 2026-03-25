# Status Report — Manual Test Run

## Run Info

| Field | Value |
|-------|-------|
| Date | 2026-03-24 |
| Executor | Claude (automated) |
| MCP tools-py version | current (branch build) |
| Branch | `112-rename_symbol-move_symbol-move_module-all-hang-indefinitely` |
| Git SHA | `46d80f0` |
| Run start | 2026-03-24 23:36:32 |
| Run end | 2026-03-24 23:53:12 |
| Total duration | 16m 40s |

## Summary

| Phase | Total | Passed | Failed | Skipped | Duration |
|-------|-------|--------|--------|---------|----------|
| Phase 1: Read-Only | 18 | 18 | 0 | 0 | ~10m 2s |
| Phase 2: Dry-Run Mutations | 3 | 0 | 3 | 0 | ~6m 0s (3×120s timeout) |
| Phase 3: Apply + Verify + Revert | 15 | 0 | 0 | 15 | 0s (all skipped) |
| **Total** | **36** | **18** | **3** | **15** | **16m 40s** |

## Per-Tool Results

| Tool | Tests | Passed | Failed | Skipped | Verdict |
|------|-------|--------|--------|---------|---------|
| `run_pylint_check` | 4 | 4 | 0 | 0 | ✅ PASS |
| `run_pytest_check` | 5 | 5 | 0 | 0 | ✅ PASS |
| `run_mypy_check` | 4 | 4 | 0 | 0 | ✅ PASS |
| `list_symbols` | 4 | 4 | 0 | 0 | ✅ PASS |
| `find_references` | 4 | 4 | 0 | 0 | ✅ PASS |
| `rename_symbol` | 5 | 0 | 1 | 4 | ❌ FAIL |
| `move_symbol` | 6 | 0 | 1 | 5 | ❌ FAIL |
| `move_module` | 6 | 0 | 1 | 5 | ❌ FAIL |

## Issues Found

### Issue 1 — `rename_symbol` hangs (BLOCKER)

- **Test**: 6a (dry run)
- **Severity**: Blocker
- **Details**: `rename_symbol(dry_run=True)` timed out after 120s. The tool never returns.
- **Impact**: Cannot rename symbols. All Phase 3 rename tests skipped.

### Issue 2 — `move_symbol` hangs (BLOCKER)

- **Test**: 7a (dry run)
- **Severity**: Blocker
- **Details**: `move_symbol(dry_run=True)` timed out after 120s. The tool never returns.
- **Impact**: Cannot move symbols. All Phase 3 move_symbol tests skipped.

### Issue 3 — `move_module` hangs (BLOCKER)

- **Test**: 8a (dry run)
- **Severity**: Blocker
- **Details**: `move_module(dry_run=True)` timed out after 120s. The tool never returns.
- **Impact**: Cannot move modules. All Phase 3 move_module tests skipped.

## Observations

### OBS-1: pytest path-based filtering ineffective

Tests 2a, 2b, 2c, 2e all collected 302 tests (full project suite) despite passing specific file/directory paths in `extra_args`. Only the `-k` keyword filter (2d) correctly limited test collection to 5 tests. This suggests that path arguments in `extra_args` are not being used to filter test collection — pytest may be configured (via `pyproject.toml` or conftest) to always discover from a root directory.

**Severity**: Minor — tests still pass, but run time is much longer than necessary when targeting specific files.

### OBS-2: list_symbols includes imported symbols

Tests 4b and 4c showed that `list_symbols` returns imported names alongside locally-defined symbols. For example, `utils.py` listed imported `DEFAULT_STATUS`, `MAX_NAME_LENGTH`, `User` in addition to its own `create_user`, `is_active`, `format_user`. The test plan expected only locally-defined symbols.

**Severity**: Minor — the tool is functional, but consumers must be aware that results include imports.

### OBS-3: No files modified by timed-out operations

Despite all three mutation tools timing out, `git diff` remained clean. The timeout handling appears safe — no partial writes occurred.

## Conclusion

**Overall verdict: FAIL**

| Question | Answer |
|----------|--------|
| All tools functional? | ❌ No — 3 of 8 tools (rename_symbol, move_symbol, move_module) hang indefinitely |
| Dry-run mode reliable? | ❌ Cannot evaluate — all dry runs timed out |
| Import rewriting correct? | ❌ Cannot evaluate — no mutations completed |
| Tests pass after mutations? | ❌ Cannot evaluate — no mutations completed |
| Clean revert possible? | ✅ Yes — timed-out operations left no file modifications |

The 5 read-only tools (`run_pylint_check`, `run_pytest_check`, `run_mypy_check`, `list_symbols`, `find_references`) are fully functional. The 3 mutation tools (`rename_symbol`, `move_symbol`, `move_module`) all hang indefinitely, confirming the issue described in #112.
