# Plan Review Log — Run 1

**Branch:** 108-add-python-refactoring-tools-rope-jedi
**Date:** 2026-03-23

## Round 1 — 2026-03-23

**Findings:**
- [Critical] `refactoring_integration` marker not registered in pyproject.toml; inconsistent with codebase convention
- [Critical] Late-binding dependency in CheckerTools closures not documented
- [High] Step 1 bundles 4 independent concerns into one commit (violates "one step = one commit")
- [High] `.importlinter` layers contract update is vague — no exact ordering specified
- [High] `tach.toml` server depends_on changes not explicit in Step 1
- [Medium] rope+jedi as core deps increases install size
- [Medium] Auto-create `__init__.py` may duplicate rope behavior
- [Medium] `_format_changes` assumes created vs modified distinction — verify rope API
- [Low] Tests not parameterized where applicable
- [Low] Manual symbol position scanning in find_references when jedi provides `get_names()`
- [Low] No Windows path handling notes

**Decisions:**
- Accept #1: Use existing `integration` marker instead of `refactoring_integration`
- Accept #2: Add clarifying note about late-binding in CheckerTools step
- Accept #3: Split Step 1 into Step 1 (scaffolding) + Step 2 (extract CheckerTools), renumber to 5 steps
- Accept #4: Specify exact `.importlinter` layer ordering in plan
- Accept #5: Make tach.toml server dependency changes explicit
- Skip #6: User confirmed core dependencies are acceptable
- Skip #7: Implementation detail — verify during coding
- Skip #8: Implementation detail — verify rope API during coding
- Accept #9: Add `@pytest.mark.parametrize` notes to test sections
- Accept #10: Use `get_names()` for symbol position in find_references
- Accept #11: Add Windows path handling note to summary

**User decisions:**
- Q1: rope+jedi as core dependencies → Confirmed (option A)
- Q2: Keep `move_module` in v1 → Confirmed (option A, all 5 tools)
- Q3: CheckerTools extraction in this PR → Confirmed (option A)

**Changes:** Split step 1, renumbered to 5 steps, updated all plan files with accepted improvements
**Status:** Committed (pending)
