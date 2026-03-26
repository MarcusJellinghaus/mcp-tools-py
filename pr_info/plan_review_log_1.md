# Plan Review Log — Issue #120

> move_symbol: from-global imports, self-import removal, batch move support

## Round 1 — 2026-03-26

**Findings**:
- Steps 2+3 tightly coupled — Step 2 creates broken transitional state (multi-element lists silently truncated)
- Dry-run algorithm for batch moves not described in Step 3
- Step 6 test numbering (7c) conflicts with existing 7c (teardown) in TEST_PLAN.md
- Missing duplicate check within `symbol_names` in validation
- "All-or-nothing" wording implies rollback that doesn't exist — only covers validation
- Step 1 rope preference name verified correct (no action)
- Self-import unconditional removal is pragmatically correct (no action)
- No from-global test for rename/move_module — YAGNI (skip)
- Steps 4+5 could merge but current split is fine (no action)
- Integration test updates correctly identified (no action)
- PROGRESS_TRACKER template update is correct (skip)

**Decisions**:
- Accept: Merge Steps 2+3 into single Step 2 (avoid broken transitional state)
- Accept: Add duplicate check to upfront validation
- Accept: Describe dry-run batch algorithm in merged step
- Accept: Clarify all-or-nothing scope = validation only
- Accept: Renumber tests to 7a-7c (single) + 7d-7f (batch)
- Accept: Renumber remaining steps (5 steps total)
- Skip: from-global tests for rename/move_module (YAGNI)
- Skip: Merging Steps 4+5 (current split is fine)

**User decisions**: None required — all findings were straightforward improvements.

**Changes**:
- Merged old Steps 2+3 into new Step 2 (batch move_symbol: signature change, loop, validation)
- Added duplicate check to validation algorithm
- Added dry-run batch algorithm description
- Clarified all-or-nothing scope in summary and Step 2
- Fixed test numbering in Step 5 (was Step 6): 7a-7c single, 7d-7f batch
- Renumbered steps: 1 (unchanged), 2 (merged), 3 (was 4), 4 (was 5), 5 (was 6)
- Deleted old step_6.md

**Status**: Committed (c1a8170)

## Round 2 — 2026-03-26

**Findings**:
- Step 1: rope preference name should note verification at implementation time
- Step 2: dry-run batch logic underspecified (source unchanged between iterations in dry-run)
- Step 2: error messages need to reference loop variable, not entire list
- Step 2: large step needs justification note (atomic signature change)
- Step 2: cleanup logic adaptation for batch mode not documented
- Step 3: unconditional self-import removal deviates from issue wording (but is correct)
- No Critical findings — plan structure is sound after Round 1

**Decisions**:
- Accept: All 6 findings — minor clarification notes for the implementing LLM
- No design/requirements questions needed

**User decisions**: None required.

**Changes**:
- Added rope API verification note to Step 1
- Added dry-run batch clarification, error message guidance, size justification, and cleanup logic docs to Step 2
- Added unconditional removal rationale to Step 3

**Status**: Committed (cd9dc10)

## Final Status

- **Rounds**: 2
- **Commits**: 2 (c1a8170, cd9dc10)
- **Plan ready for approval**: Yes
- **Open questions**: None
- **Summary**: Round 1 merged tightly-coupled steps, fixed test numbering conflicts, and clarified validation scope. Round 2 added minor implementation notes. No design or requirements questions needed user input.

