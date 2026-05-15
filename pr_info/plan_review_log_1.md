# Plan Review Log #1 — Issue #201

**Branch:** `201-chore-split-checker-tools-py-and-test-integration-formatting-py`
**Base:** `main`
**Date:** 2026-05-15
**Scope:** Split `checker_tools.py` (893 lines) and `test_integration_formatting.py` (814 lines); remove 3 stale `.large-files-allowlist` entries.

Plan files under review:
- `pr_info/steps/summary.md`
- `pr_info/steps/step_1.md`
- `pr_info/steps/step_2.md`

## Round 1 — 2026-05-15

**Findings (from engineer review):**
1. **CRITICAL** — Plan moves `_format_pylint_result`, `_format_mypy_result`, `_format_pytest_result_with_details` from `CheckerTools` to module-level free functions, but lists 4 test files as "unchanged." ~40 call sites use `CheckerTools(server)._format_*(...)` as instance methods — they would break.
2. **CRITICAL** — 13 `patch("mcp_tools_py.checker_tools.check_code_with_pytest")` sites in `test_server_params.py` + `test_tool_availability.py` (latter not even in plan), plus `patch(...)` for `run_vulture`, `run_tach`, `run_ruff_check_impl`, `resolve_target_directories`, etc. After the split these patches target the wrong namespace.
3. **CRITICAL** — "Unchanged callers" list in `summary.md` is misleading; `test_server_params.py`, `test_tool_availability.py`, `test_checker_tools.py`, `test_code_checker_bandit/test_integration.py` must be reclassified as Modified.
4. **ACCEPT** — Step 1 missing test-count sanity check (Step 2 has one).
5. **ACCEPT** — `from tests.test_code_checker_pytest.conftest import ...` is a pytest anti-pattern; move helpers to a sibling `_helpers.py`.
6. **SKIP** — Step sizing OK; sub-split fallback well-defined; importlinter package-scoped carve-out confirmed.

**Decisions:**
- Finding 1: escalated to user — see User decisions below.
- Findings 2, 3, 4, 5: auto-accepted (correctness fixes / anti-pattern cleanup).
- Finding 6: skipped (no action needed).

**User decisions:**
- **Q: How to handle `_format_*` helper migration?** **A: Keep as `CheckerTools` methods** (preserves all 40+ existing test call sites). Closures in `*_tool.py` receive the orchestrator instance instead of just `server`, so `register(mcp, checker_tools)` replaces `register(mcp, server)`.

**Changes applied:**
- `summary.md` — formatters stay on `CheckerTools`; new `register` signature; reclassified 4 test files as Modified; added `_helpers.py` for shared test helpers.
- `step_1.md` — updated `__init__.py` template (`_format_*` retained as methods); new `register(mcp, checker_tools)` signature; added patch-site retargeting inventory with line numbers; added test-count sanity check.
- `step_2.md` — helpers move to sibling `_helpers.py`, not `conftest.py`; conftest holds fixtures only.

**Status:** Plan revisions applied — ready to commit; further review round required (changes were made).

## Round 2 — 2026-05-15

**Findings (from engineer review):**
1. **ACCEPT** — `test_server_params.py` patch-site count says 13, actual is 11 (enumerated line list is correct).
2. **ACCEPT** — `test_checker_tools.py` inventory: `run_vulture` count is 3, actual is 4 (missing line 345); `resolve_target_directories` text says 11 but list has 13.
3. **SKIP** — `register(mcp, checker_tools)` threading confirmed correct.
4. **SKIP** — `_helpers.py` placement confirmed correct (no circular dependency).
5. **Verdict from engineer:** READY_TO_APPROVE; findings 1–2 are non-blocking inventory tidy-ups.

**Decisions:**
- Findings 1, 2: auto-accepted (mechanical inventory accuracy fixes; trivial).
- Findings 3, 4: no action needed.

**User decisions:** None — no escalations needed this round.

**Changes applied:**
- `summary.md` — corrected `test_server_params.py` count 13 → 11.
- `step_1.md` — corrected `test_server_params.py` count 13 → 11; `run_vulture` 3 → 4 with line 345 added; `resolve_target_directories` 11 → 13. All line numbers re-verified against current code.

**Status:** Plan revisions applied — ready to commit; further review round required (changes were made).

## Round 3 — 2026-05-15

**Findings (from engineer review):** None — plan is correct and ready.
- Re-verified patch-site counts (`run_vulture` 4 sites, `resolve_target_directories` 13 sites, `check_code_with_pytest` 11 sites) against current code: all match.
- Re-verified 9+2 test allocation in `test_integration_formatting.py`: all method names match.
- Re-verified stale allowlist entry `test_integration_show_details.py`: file truly absent.
- Design consistency across `summary.md`, `step_1.md`, `step_2.md` confirmed.

**Decisions:** Accept verdict — no changes.

**User decisions:** None.

**Changes applied:** None.

**Status:** No plan changes this round — loop terminates.

## Final Status

**Rounds run:** 3
**Verdict:** READY_TO_APPROVE
**Commits produced on this branch (review):**
- `03e41ae` — `docs(pr_info): apply review round 1 revisions for #201`
- `12a4646` — `docs(pr_info): fix patch-site inventory counts (review round 2)`
- (one more for this final log update)

**Key design pivots locked in:**
- Formatter helpers (`_format_pylint_result`, `_format_mypy_result`, `_format_pytest_result_with_details`) stay as methods on `CheckerTools` in `__init__.py` (user decision).
- Per-tool entry point: `register(mcp, checker_tools)` — closures access the orchestrator's `_server` and `_format_*`.
- Patch-site inventory enumerated for `test_server_params.py` (11), `test_tool_availability.py` (2), `test_checker_tools.py` (20+ across multiple symbols), `test_code_checker_bandit/test_integration.py`.
- Shared test helpers live in `tests/test_code_checker_pytest/_helpers.py` (not conftest) to avoid the conftest-import anti-pattern; conftest holds fixtures only.
- existing `.importlinter` carve-out `mcp_tools_py.checker_tools -> mcp_tools_py.server` covers the new package — no changes needed.

**Plan is ready for implementation approval.**
