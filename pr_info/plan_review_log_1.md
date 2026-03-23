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
**Status:** Committed (fe706f8)

## Round 2 — 2026-03-23

**Findings:**
- [High] `integration` marker not registered in pyproject.toml — will cause PytestUnknownMarkWarning
- [High] Pipe-separated `.importlinter` syntax needs verification note
- [High] tach.toml server deps changed in Step 1 before `checker_tools.py` exists in Step 2 — tach_check would fail
- [Medium] Server __init__ should reorder resolution before registration
- [Medium] No rope exception handling strategy documented
- [Medium] `test_move_symbol_name_collision` body is empty
- [Medium] Asymmetry between RefactoringTools and CheckerTools interfaces
- [Medium] FastMCPProtocol location with TYPE_CHECKING guard
- [Low] find_references output format over-specified
- [Low] No `__all__` in refactoring __init__.py
- [Low] Empty test directory in Steps 1-2
- [Low] vulture_whitelist.py may need updates
- [Low] sample_project fixture path consistency

**Decisions:**
- Accept H1: Add `integration` marker registration to pyproject.toml in Step 1
- Accept H2: Add pipe syntax verification note for .importlinter
- Accept H3: Defer server tach.toml dependency swap to Step 2
- Accept M1: Reorder server __init__ — resolution before registration
- Accept M3: Add rope exception handling note to Step 4
- Accept M4: Flesh out test_move_symbol_name_collision
- Skip M2: Asymmetry is acceptable for v1
- Skip M5: TYPE_CHECKING guard is sufficient, pre-existing pattern
- Skip L1-L5: Informational, no action needed

**User decisions:** None required this round
**Changes:** Applied 6 fixes across steps 1, 2, and 4
**Status:** Committed (pending)
