# Plan Review Log — Issue #10

**Feature**: Add `run_format_code` MCP tool (black + isort) + rename server
**Branch**: `10-feat-add-run-format-code-mcp-tool-black-isort-rename-server`
**Date**: 2026-03-30

---

## Round 1 — 2026-03-30

**Findings**:
- (Critical) `.importlinter` not updated for new `formatter` module — would cause `lint-imports` failures
- (Critical) Redundant `mcp_tools_py.utils.project_config` tach entry — `exact = false` means parent covers submodules
- (Accept) `_truncate_output` duplicated in black_runner and isort_runner — pragmatic for 6 lines, YAGNI
- (Accept) `check_only` error-handling ambiguity — implementer can resolve without plan changes
- (Accept) Availability check approach consistent with existing pattern
- (Accept) Step sizing appropriate — 4 well-scoped steps
- (Accept) Moving black/isort to main dependencies correct for runtime use
- (Accept) Test file placement follows existing flat pattern
- (Accept) isort `--check-only` flag difference correctly documented
- (Accept) Server rename scope complete

**Decisions**:
- Critical 1: Accept — added `.importlinter` to step 4 (layers, ignore_imports, forbidden_modules)
- Critical 2: Accept — removed redundant `utils.project_config` tach entry from step 4
- All Accept items: no plan changes needed

**User decisions**: None required — both critical findings were straightforward config gaps

**Changes**: Updated `pr_info/steps/step_4.md`:
- Added `.importlinter` to WHERE table and WHAT section (items 11-13)
- Removed redundant `utils.project_config` tach entry
- Renumbered items
- Updated LLM Prompt section

**Status**: Committed (e305aba)

---

## Round 2 — 2026-03-30

**Findings**:
- (Low) Availability check pattern diverges from lint-imports/vulture — intentional, better approach
- (High) Step 3 uses `ToolServer` before step 4 renames it — would fail mypy/pylint
- (Low) FormatterTools follows CheckerTools pattern — appropriate
- (Low) Summary return type outdated vs step 1's `TargetDirs`
- (Low) Duplicate `_truncate_output` — acceptable per KISS
- (Medium) check_only cannot distinguish formatting-needed from crash
- (Medium) Step 4 test update scope underspecified
- (Low) Step 1 doesn't specify both exports for `utils/__init__.py`
- (Low) Empty `__init__.py` then modified next step — fine
- (Low) Dependency move timing — acceptable since dev deps installed

**Decisions**:
- Finding 2 (High): Accept — fixed step 3 to use `CodeCheckerServer`, step 4 will rename
- Finding 4 (Low): Accept — updated summary.md return type to `TargetDirs`
- Finding 6 (Medium): Accept — simplified check_only to always continue regardless of exit code
- Finding 7 (Medium): Accept — added note about ~8-10 dict literals needing updates in step 4
- Finding 8 (Low): Accept — step 1 now explicitly lists both exports
- Findings 1, 3, 5, 9, 10: Skip — no changes needed

**User decisions**: None required — all findings were straightforward

**Changes**: Updated `pr_info/steps/step_3.md`, `step_4.md`, `step_1.md`, `summary.md`

**Status**: Committed (fade566)

---

## Round 3 — 2026-03-30 (verification)

**Findings**: None — plan is internally consistent across all steps and summary.
**Decisions**: N/A
**User decisions**: N/A
**Changes**: None
**Status**: No changes needed

---

## Final Status

- **Rounds**: 3 (2 with changes, 1 verification)
- **Commits**: 2 (`e305aba` round 1, `fade566` round 2)
- **Plan status**: Ready for approval
- **Issues fixed**: `.importlinter` gap, redundant tach entry, step ordering (ToolServer→CodeCheckerServer), check_only simplification, summary consistency, test scope clarity, explicit exports

