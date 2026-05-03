# Plan Review Log — Run 1

**Issue:** #187
**Date started:** 2026-05-03
**Branch:** 187-pytest-exit-codes-3-4-5-swallow-pytest-output-cannot-diagnose-crash

## Round 1 — 2026-05-03
**Findings**:
- Stale `tools/format_all.sh` reference (script removed in 3506e6e).
- Wrong MCP tool names in Quality gates code block (`mcp__tools-py__*` → `mcp__mcp-tools-py__*`).
- Over-engineered/stale pytest marker filter (long `not git_integration and not claude_cli_integration ...`); repo only documents the `integration` marker.
- Test placement reference: insertion point should be after `test_run_tests_skip_default_test_folder` AND its sibling `test_run_tests_default_test_folder_appended`.
- Open design question: `print()` cleanup scope — only the 3 named branches, or all `print()` in `run_tests`?
- Open design question: should the test assert logger emission via `caplog`?
- TASK_TRACKER.md is empty (intentional per planning_principles — populated at implementation step 0).

**Decisions**:
- Auto-accept: drop `format_all.sh` reference, fix tool names, simplify marker filter, tighten test placement wording.
- Ask user: print scope, caplog assertion.

**User decisions**:
- Print scope: **B) Convert all `print()` in `run_tests` in this commit.**
- Caplog: **B) Add `caplog` assertion per branch.**

**Changes**:
- `pr_info/steps/summary.md`: rewrote Problem + Fix to cover all `print()` sites in `run_tests`; added per-line table; explicit out-of-scope note for other checkers.
- `pr_info/steps/step_1.md`: expanded Goal/TDD; added Mechanical conversions block for the print-only sites; rewrote test to use `caplog` and assert one `WARNING` per branch + log_substring parametrize column; replaced `format_all.sh` with `mcp__mcp-tools-py__run_format_code`; fixed `mcp-tools-py` tool names; replaced long marker filter with `-m "not integration"`; tightened insertion-point wording.

**Status**: changes applied, not yet committed (batched).

## Round 2 — 2026-05-03
**Findings**:
- LLM-visibility audit: MCP caller path is `{"success": False, "error": str(e)}` — only exception text reaches the LLM. Round-1 expansion converted prints to `logger.warning` at sites that still raised generic exceptions, so LLM was still blind at lines 271 (install fail), 289 (retry timeout), 384 (no-report-file fallback).

**Decisions**:
- Ask user: extend `_build_error_detail(...)` to expanded sites, or stop at logger-only?

**User decisions**:
- **B) Full LLM-visibility fix at every raising site.** No new helper.

**Changes**:
- `pr_info/steps/summary.md`: stated LLM-visibility principle explicitly; added rows for 271 and 384 to per-line table; updated 289 row; "Principle" callout listing 6 sites + already-correct 311; updated Modified-files note from 3 → 6 raising branches.
- `pr_info/steps/step_1.md`: expanded Goal to enumerate all 6 raising paths; rewrote TDD step 1 (cover all 6, allow split) and step 2 (per-site instructions); added Before/After code blocks for 271, 289, 384; expanded Test section into Test #1 (returncode + 384) and Test #2 (install_fail + retry_timeout via `side_effect`); broadened HOW to include `TimeoutError` and the new branch labels.

**Status**: changes applied, not yet committed (batched).

## Round 3 — 2026-05-03
**Findings**:
- Round-1 print() inventory was incomplete: 5 missed sites (~205, 213, 221, 247, 283) plus the no-report-file `print(combined_output)` at ~360.
- 2 missed early raising paths inside `run_tests`: line ~217 `raise RuntimeError(subprocess_result.execution_error)` (caller gets only `execution_error` string, no stdout/stderr) and line ~223 `raise TimeoutError(...)` (no stdout/stderr).
- Test #2 snippet had confused control flow (assertions inside one branch, leaving the other untested).
- Line-309 `print("No tests found, raising specific exception")` is tautological with the next-line raise.
- Test #1 no-report-file row didn't specify how to trigger line 384.

**Decisions**:
- Auto-accept: include all missed print sites, add early raising paths to LLM-visibility set, rewrite Test #2 with clean if/else, drop tautological line-309 message, specify `os.path.isfile` mock for the no-report row.
- Ask user: per-site log levels for the 5 newly-included operational/debug prints.

**User decisions**:
- **B) Per-site log levels:** 205/213/247/283 → `logger.debug`; 221 → `logger.warning`; 360 → `logger.warning` (real swallowed pytest output).

**Changes**:
- `pr_info/steps/summary.md`: per-line table expanded to all 16 sites with explicit log-level column; rewrote Principle as 3-part (warning for pytest output / debug for operational / `_build_error_detail` for every raise); raising-path set now 217, 223, 271, 289, 337, 343, 355, 384; line-309 marked deleted; updated Modified-files block, Plan row, Fix paragraph, architectural-notes.
- `pr_info/steps/step_1.md`: updated Goal with 217/223 verification notes; added 210/221/230/247/278/309-deleted to TDD step 2; rewrote WHERE listing all 16 sites with levels; rewrote WHAT/Mechanical block grouping by level + Before/After for early-raise paths; updated Test #1 parametrize with execution_error/subprocess_timeout/no_report_file rows + `os.path.isfile` patch; rewrote Test #2 with clean if/else for `side_effect` building and shared assertions; added "illustrative; rewrite at implementation time" callouts.

**Source verification (round 3)**:
- Line 217 `RuntimeError(execution_error)`: `execution_error` is a separate `CommandResult` field (verified across all callers), does NOT include stdout/stderr. Append `_build_error_detail(stdout, stderr)`.
- Line 223 `TimeoutError`: `subprocess_runner` captures partial stdout/stderr before timeout; same fields available. Append `_build_error_detail(...)`.
- Line ~363 print → 384 raise: same branch (`if not report_exists`); converting print to `logger.warning` aligns with the new principle.
- Line-number drift: round-3 review noted plan says ~217/~223 for two early-raise sites; actual source is ~226/~232. Code identification is textually unambiguous; line-number drift is cosmetic and self-correcting at implementation.

**Status**: changes applied, not yet committed (batched).

## Final Status
- 3 review rounds run, plan converged.
- Plan is **ready for implementation**.
- All design decisions resolved with the user (print scope, caplog, LLM-visibility for expanded sites, log levels per site).
- Final scope: single step, single commit; covers `run_tests` in `runners.py` only; 16 print sites converted (11 → `logger.warning`, 4 → `logger.debug`, 1 deleted); 8 raising paths surface real stdout/stderr via `_build_error_detail`; two parametrized tests assert both raised-exception text and `caplog` warning records.
- Outstanding cosmetic nits to fix at implementation time: line numbers ~217/~223 drifted to ~226/~232; one illustrative mock-stderr string doesn't match the live missing-plugin regex (snippet explicitly marked illustrative).
- Other checkers (pylint/mypy/ruff/bandit/etc.) explicitly out of scope.
