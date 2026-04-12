# Step 4: Final verification and stale-import grep

**Ref:** [summary.md](summary.md) | **Issue:** #152 | **Commit:** `adopt: verify no stale imports remain`

## Goal

Verify the migration is complete. Grep for any stale import paths that were missed. Confirm all checks pass.

## LLM Prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_4.md`.
> Implement step 4: grep all `.py` files for stale import paths. Fix any remaining occurrences. Run all quality checks.

## WHAT — Verification checks

### Stale import grep

Search all `.py` files for these patterns (excluding the two shim files):

1. `from mcp_tools_py.utils.subprocess_runner import` — should only appear in:
   - `src/mcp_tools_py/utils/__init__.py` (imports from the local shim)
2. `from mcp_tools_py.log_utils import` — should appear **nowhere** (shim has no internal consumers)
3. `import mcp_tools_py.utils.subprocess_runner` — should appear nowhere
4. `import mcp_tools_py.log_utils` — should appear nowhere

### Expected results

Any match outside the shim files and `utils/__init__.py` is a bug — fix the import.

### Quality checks

- [ ] pylint passes
- [ ] pytest passes (unit tests, excluding integration markers)
- [ ] mypy passes
- [ ] No stale imports found (or all fixed)
- [ ] `./tools/format_all.sh` has been run

## DATA — No code changes expected

This step should be a no-op if steps 1-3 were done correctly. If any stale imports are found, fix them using the same pattern as steps 1-2.
