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

**Status**: Ready to commit

