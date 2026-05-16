# Implementation Review Log 1 — Issue #201

Branch: `201-chore-split-checker-tools-py-and-test-integration-formatting-py`
Base: `main`
Scope: Split `src/mcp_tools_py/checker_tools.py` into a package + split `tests/test_code_checker_pytest/test_integration_formatting.py` by source mapping. Remove three `.large-files-allowlist` entries.

Reviewing against:
- GitHub issue #201
- `pr_info/steps/summary.md`
- `.claude/knowledge_base/software_engineering_principles.md`
- `.claude/knowledge_base/python.md`


## Round 1 — 2026-05-16

**Findings** (from review subagent):

1. `.importlinter` adds `mcp_tools_py.checker_tools.** -> mcp_tools_py.server` — deviates from summary.md ("no `.importlinter` change").
2. `_format_pytest_result_with_details` signature in summary.md lists a `return_code` param the implementation does not have (and never had).
3. Step 1 patch-site inventory listed `create_prompt_for_failed_tests` → `pytest_tool`, but implementation correctly keeps it at `checker_tools` (symbol is bound in `__init__.py`).
4. `mcp-coder check file-size` reports 5 stale allowlist entries unrelated to this PR.
5. `test_reporting.py` = 472 lines, `test_runners.py` = 143 lines — both under 750. No sub-split.
6. `__init__.py` does runtime imports of all 9 `*_tool` submodules (matches design; pre-refactor `checker_tools.py` already imported everything eagerly).
7. `__init__.py` is well-scoped: `__all__ = ["CheckerTools"]`.
8. 9 `*_tool.py` modules present with uniform shape (one `register(mcp, checker_tools)` function each, TYPE_CHECKING-only `FastMCPProtocol`/`CheckerTools` imports).
9. Patch-site retargeting verified across `test_checker_tools.py`, `test_server_params.py`, `test_tool_availability.py`, `test_code_checker_bandit/test_integration.py`.
10. `conftest.py` (fixtures) and `_helpers.py` (project-builders) match design; helpers imported from `_helpers`, not `conftest` — anti-pattern avoided.
11. `.large-files-allowlist`: 3 entries removed exactly as designed; no new entries.

**Decisions** (supervisor):

1. **SKIP** — the `**` line is *necessary*: each submodule has a `TYPE_CHECKING` import `from mcp_tools_py.server import FastMCPProtocol`, and the existing parent-only rule does not cover submodules. The summary was wrong; the implementation is right. Commit `6eded4f` documents the addition.
2. **SKIP** — `summary.md` doc-bug only; implementation matches the pre-refactor signature. `pr_info/` is discarded later, so no fix-up worthwhile.
3. **SKIP** — implementation is correct (symbol is bound in `__init__.py`, so patching the parent namespace works). Plan inventory bug only.
4. **SKIP** — explicitly out of scope per `summary.md`.
5–11. **ACCEPT** — confirmations of correct implementation, no action required.

**Changes**: None.

**Tool results** (engineer): `run_pylint_check` PASS · `run_mypy_check` (strict) PASS · `run_pytest_check` (`-n auto -m "not integration"`) PASS (530 collected, 529 passed, 1 skipped) · `run_lint_imports_check` PASS · `run_vulture_check` PASS · `check_file_size` (max 750) PASS.

**Status**: No changes needed. Loop converges in round 1.


## Final Status

- Review rounds run: **1** (converged immediately — zero code changes)
- Code changes by supervisor: **none**
- Supervisor-run checks: `run_vulture_check` PASS · `run_lint_imports_check` PASS (3 contracts kept, 0 broken; 93 files / 286 dependencies analysed)
- Verdict: **Implementation matches the design.** Ready to merge.
