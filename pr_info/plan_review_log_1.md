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
