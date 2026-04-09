# Implementation Review Log — Run 1

Issue: #104 — Add ruff MCP tools (check + fix) for linting
Branch: 104-add-ruff-mcp-tools-check-fix-for-linting

## Round 1 — 2026-04-09

**Findings:**
- RuffResult model defined but never used (YAGNI)
- tach.toml declares log_utils dependency but no import exists
- Missing @log_function_call on runner functions (inconsistent with pylint)
- run_ruff_fix_impl reports files as "changed" before fix runs
- No handler-level tests for ruff tools in test_checker_tools.py
- Grammar pluralization in report output
- Missing project_dir validation in runners
- target_directories not validated in runners
- Reporting module lacks logging instrumentation

**Decisions:**
- Accept: Remove RuffResult (YAGNI)
- Accept: Add @log_function_call to runners, making log_utils dependency real
- Accept: Add handler-level tests for ruff in test_checker_tools.py
- Accept: Add project_dir validation to runners
- Skip: Fix reporting files pre-check (design choice, bounded complexity)
- Skip: Grammar pluralization (cosmetic, LLM-facing)
- Skip: target_directories validation (caller already validates)
- Skip: Reporting logging (pure formatting functions)

**Changes:**
- Removed RuffResult from models.py and __init__.py
- Added @log_function_call to run_ruff_check_impl and run_ruff_fix_impl
- Added project_dir validation (FileNotFoundError) to both runners
- Added 6 handler-level tests in test_checker_tools.py
- Updated test_runners.py to mock os.path.isdir + added validation tests

**Status:** Committed (ca02ac3)

## Round 2 — 2026-04-09

**Findings:**
- Critical: run_ruff_fix_impl silently discards parse errors from pre-check and does not handle exit code 2
- Accept: Post-fix parse error also silently discarded

**Decisions:**
- Accept (Critical): Add exit code 2 handling and parse error propagation to pre-check step
- Accept: Add error propagation for post-fix parse step

**Changes:**
- Added exit code 2 handling after both pre-check and fix subprocess calls
- Changed parse error from discarded (_) to propagated (parse_error) in both parse calls
- Added 4 tests covering all new error paths in test_runners.py

**Status:** Committed (cf7125d)

## Round 3 — 2026-04-09

**Findings:** None — code is clean and ready for merge.
**Decisions:** N/A
**Changes:** None
**Status:** No changes needed

## Final Status

Review complete after 3 rounds. All findings addressed. Two commits produced:
- ca02ac3: Remove unused RuffResult, add logging/validation to runners, add handler tests
- cf7125d: Add error handling for exit code 2 and parse errors in fix impl

No remaining issues. Code is consistent with established patterns and ready for merge.
