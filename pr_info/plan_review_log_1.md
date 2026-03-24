# Plan Review Log — Run 1

**Issue**: #112 — Fix rope-based mutation tools hanging indefinitely
**Branch**: 112-rename_symbol-move_symbol-move_module-all-hang-indefinitely
**Date**: 2026-03-24

## Round 1 — 2026-03-24

**Findings**:
- [Critical] Step 1 is prep-only plumbing with no tangible behavior change — violates "every step must have tangible results"
- [Critical] Step 3's gitignore-to-rope pattern conversion is under-specified — rope uses its own pattern format, not gitignore
- [Critical] Multiprocessing on Windows: each `_*_impl` must create its own rope `Project` in the subprocess
- [Accept] Steps 2 and 3 are tiny/intertwined, both modify `_with_rope_project()` — merge them
- [Accept] No `test_server.py` exists for testing constructor — moot after merging step 1 into step 4
- [Accept] `Queue.get()` must be called before `process.join()` to avoid Windows pipe deadlock
- [Accept] Timeout tests need 3-5s timeout with cleanup in `finally` block
- [Accept] Need note that `rope_tools.py` has no top-level side effects (safe for `spawn`)
- [Skip] Plan uses `pathspec` vs issue's `igittigitt` — addressed by user decision
- [Skip] Existing tests don't pass `timeout` — default value handles it

**Decisions**:
- Accept: Merge step 1 (plumbing) into step 4 (timeout) — one step must have tangible result
- Accept: Merge step 2 (cache) and step 3 (gitignore) — intertwined, same function
- Accept: All technical fixes for Windows multiprocessing (queue ordering, cleanup, picklability)
- Ask user: Drop gitignore parsing in favor of hardcoded defaults? (options A/B/C)

**User decisions**:
- User chose option B: keep gitignore parsing, but copy code ONE-TO-ONE from p_workspace using `igittigitt` (not `pathspec`). Add comment that code is copied and should be refactored.

**Changes**:
- Restructured plan from 4 steps to 2 steps
- Step 1: Disable cache + gitignore filtering (merged old steps 2+3), uses `igittigitt` copied from p_workspace
- Step 2: Timeout wrapper + CLI plumbing (merged old steps 1+4), with Windows-specific technical details
- Deleted step_3.md and step_4.md
- Updated summary.md with new structure and `igittigitt` decision

**Status**: Ready to commit
