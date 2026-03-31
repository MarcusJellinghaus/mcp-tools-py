# Plan Review Log — Run 1

**Issue:** #136 — Use pyproject.toml auto-detection for target_directories in checker tools
**Date:** 2026-03-31
**Branch:** 136-refactor-use-pyproject-toml-auto-detection-for-target-directories-in-checker-tools

## Round 1 — 2026-03-31

**Findings**:
- **Critical #1**: `formatter_tools.py` has the same inline directory resolution pattern — should use the new shared `resolve_target_directories()` helper (DRY violation)
- **Critical #2**: Intermediate functions `get_pylint_prompt()` and `get_mypy_prompt()` in reporting.py also accept `Optional[list[str]]` — must update signatures to `list[str]` to match runner changes, otherwise mypy fails
- **Critical #3**: Step 3 removes `test_vulture_whitelist_auto_included` but doesn't replace it — whitelist handoff from checker_tools to runner still needs test coverage
- **Accept #1**: Vulture runner `whitelist_path: str | None` interface is clean
- **Accept #2**: Step sizing (3 steps, 3 commits) is appropriate
- **Accept #3**: Vulture runner being dead code between Steps 2-3 is acceptable within a single PR
- **Accept #4**: Mock-based testing for `resolve_target_directories` wrapper is appropriate
- **Accept #5**: `list[str] | str` return type matches existing formatter convention
- **Accept #6**: No pyproject.toml or mypy override changes needed
- **Skip #1**: `tach.toml` `log_utils` dependency follows existing convention
- **Skip #2**: No `__init__.py` re-export needed — direct import is the pattern

**Decisions**:
- Critical #1: Accept — add formatter_tools.py refactoring to Step 3 (Boy Scout Rule, DRY)
- Critical #2: Accept — add reporting.py signature updates to Step 3 (correctness, mypy would fail without)
- Critical #3: Accept — replace removed test with `test_vulture_passes_whitelist_to_runner` in Step 3

**User decisions**: None needed — all findings were straightforward improvements.

**Changes**:
- Updated `pr_info/steps/step_3.md`: added reporting.py and formatter_tools.py to WHERE/WHAT sections, replaced whitelist test removal with replacement test, updated LLM prompt
- Updated `pr_info/steps/summary.md`: added 3 files to Files Modified table
- Created `pr_info/steps/Decisions.md` documenting rationale

**Status**: committed (2350106)

## Round 2 — 2026-03-31

**Findings**:
- **Critical #1**: Wrong path for `formatter_tools.py` — actual file is at `formatter/formatter_tools.py`, not `formatter_tools.py`. Would cause implementation to fail.
- **Accept #1**: Step 3 size is reasonable despite additions — all changes are tightly coupled
- **Accept #2**: Plan should note removing unused `get_target_directories` import from formatter_tools.py (LLM will handle naturally)
- **Accept #3-#7**: Round 1 fixes verified correctly applied; plan is internally consistent; signatures match actual code
- **Skip #1**: Steps 1 and 2 are clean, no issues

**Decisions**:
- Critical #1: Accept — fix path in summary.md and step_3.md (3 occurrences)

**User decisions**: None needed.

**Changes**:
- Fixed `formatter_tools.py` path to `formatter/formatter_tools.py` in summary.md and step_3.md (WHERE, WHAT, LLM Prompt sections)

**Status**: pending commit
