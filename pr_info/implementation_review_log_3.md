# Implementation Review Log 3 — Issue #112

**Branch:** 112-rename_symbol-move_symbol-move_module-all-hang-indefinitely
**Reviewer:** Automated supervisor + engineer subagent

## Round 1 — 2026-03-25
**Findings**:
- #1 [Critical] `read_gitignore_rules` logs gitignore content at INFO level — noisy
- #2 [Critical] `_run_rope_subprocess` error path discards structured JSON errors from rope_cli (prints to stdout, but caller only checks stderr)
- #3 [Critical] Architecture docs stale after subprocess change
- #4 [Accept] `_build_ignored_resources` does full os.walk every call
- #5 [Accept] `read_gitignore_rules` returns unused second value
- #6 [Accept] Tests for parse_args misplaced in test_rope_tools.py
- #7 [Accept] Missing encoding="utf-8" on open() call
- #8 [Accept] igittigitt not in architecture docs

**Decisions**:
- #1: Accept — lower to DEBUG
- #2: Accept — parse stdout JSON on non-zero exit before falling back to stderr
- #3: Skip — docs update out of scope for bug-fix branch
- #4: Skip — premature optimization, already in subprocess
- #5: Accept — simplify return type to just the matcher
- #6: Skip — organizational, low impact
- #7: Accept — consistency with rest of codebase
- #8: Skip — docs, out of scope

**Changes**:
- Lowered 3x logger.info → logger.debug in read_gitignore_rules
- _run_rope_subprocess: parse stdout JSON on non-zero exit code before falling back to stderr
- Simplified read_gitignore_rules to return `Callable | None` instead of tuple; updated caller
- Added encoding="utf-8" to open() call

**Status**: committed

## Round 2 — 2026-03-25
**Findings**:
- #1 [Critical] tach.toml missing `utils` dependency for refactoring module
- #2 [Suggestion] _move_symbol_impl doesn't clean up created files on error
- #3 [Suggestion] Architecture diagram stale after subprocess change
- #4 [Suggestion] read_text()/write_text() missing encoding="utf-8"
- #5 [Suggestion] Dead try/except in rope_cli.py
- #6 [Suggestion] Duplicate hang-regression tests

**Decisions**:
- #1: Accept — would break tach check in CI
- #2: Accept — functional gap: empty files persist on rope failure
- #3: Skip — docs out of scope (already skipped round 1)
- #4: Accept — consistency, bounded effort
- #5: Accept — dead code removal
- #6: Skip — hang tests are the regression safety net for this branch's core issue

**Changes**:
- Added `{ path = "mcp_tools_py.utils" }` to tach.toml refactoring module
- Added created_dest flag + cleanup in _move_symbol_impl except block
- Added encoding="utf-8" to all read_text()/write_text() calls
- Removed dead try/except in rope_cli.py

**Status**: committed
