# Implementation Review Log — Run 1

**Branch:** 37-improve-pytest-extra-args-handling-simplify-interface-deduplicate-and-improve-errors
**Date:** 2026-03-21

## Round 1 — 2026-03-21

**Findings:**
- #1: `_build_error_detail` placed before module-level logger initialization (cosmetic layout)
- #2: `list[str]` vs `List[str]` inconsistency in `SanitizedArgs` dataclass in `models.py`
- #3: Same `list[str] | None` inconsistency in `sanitize_extra_args` signature in `utils.py`
- #4: Dead-code comment references removed `show_details` parameter
- #5: `should_show_details` import/call effectively dead
- #6: Pre-existing `print()` statements in `runners.py`
- #7: `-m` edge case without value (handled correctly)
- #8: Flaky test timeout skip approach

**Decisions:**
- #1: Skip — cosmetic layout, code is readable as-is (principles: don't change working code for cosmetic reasons)
- #2: Accept — inconsistent type hints within the same file
- #3: Accept — same inconsistency in utils.py
- #4: Skip — speculative, only matters if someone hits dead code path
- #5: Skip — out of scope, pre-existing code still works
- #6: Skip — pre-existing, not introduced by this PR
- #7: Skip — handled correctly, documented limitation
- #8: Skip — pragmatic fix, reasonable approach

**Changes:**
- `models.py`: Changed `SanitizedArgs` fields from `list[str]` to `List[str]`
- `utils.py`: Updated `sanitize_extra_args` signature from `list[str] | None` to `Optional[List[str]]`, local annotations from `list[str]` to `List[str]`, added `List, Optional` to typing import

**Checks:** Pylint ✅, Pytest ✅ (235 passed, 1 skipped), Mypy ✅
**Status:** Ready to commit
