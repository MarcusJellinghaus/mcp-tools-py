# Step 1 — `pyproject.toml`: bump mypy floor + add `[typecheck]` extra

**Reference:** `pr_info/steps/summary.md` (issue #182).
**Commit:** one — `pyproject.toml` only.

## WHERE
- **File:** `pyproject.toml`
- Lines affected: line 29 (under `[project] dependencies`) and the `[project.optional-dependencies]` block (insertion).

## WHAT
Two atomic edits to `pyproject.toml`:

1. **Bump runtime mypy floor**, line 29:
   - From: `"mypy>=1.9.0",`
   - To:   `"mypy>=1.13.0",`

2. **Add `typecheck` optional-dependencies entry** under `[project.optional-dependencies]` (alongside the existing `dev = [...]` block):
   ```toml
   typecheck = ["mypy>=1.13.0"]
   ```

No other lines change. The `[dev]` block stays as-is (it does not list mypy; mypy lives in main `[dependencies]`).

## HOW
- No imports, decorators, or code wiring.
- The `[typecheck]` extra is consumed externally by `.github/workflows/upstream-mypy-check.yml` (created in step 4) via `uv pip install --system ".[typecheck]"`.
- The duplication of `mypy>=1.13.0` between `[dependencies]` and `[typecheck]` is intentional (see summary, "Architectural notes").

## ALGORITHM
N/A — TOML edit, no logic.

## DATA
N/A — packaging metadata only.

## Verification (this step)

Run all three mandatory MCP checks per CLAUDE.md after editing:

```
mcp__tools-py__run_pylint_check
mcp__tools-py__run_pytest_check    (extra_args ["-n", "auto", "-m", "not git_integration and not claude_cli_integration and not claude_api_integration and not formatter_integration and not github_integration and not langchain_integration"])
mcp__tools-py__run_mypy_check
```

Expected: all green. Mypy is the meaningful signal here — the bump from `>=1.9.0` to `>=1.13.0` could surface new strict-mode regressions on the existing codebase. If mypy flags new issues, fix them in this same step before committing (per CLAUDE.md).

## LLM Prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`. Implement step 1 only.
>
> Make exactly two edits to `pyproject.toml`:
> 1. Change line 29 from `"mypy>=1.9.0",` to `"mypy>=1.13.0",`.
> 2. Add a `typecheck = ["mypy>=1.13.0"]` line under `[project.optional-dependencies]`, alongside the existing `dev = [...]` entry.
>
> Do not touch any other line. Do not modify `src/` or `tests/`.
>
> After editing, run all three MCP code-quality checks (`run_pylint_check`, `run_pytest_check` with the standard fast-unit-test marker exclusion, `run_mypy_check`). All must pass. If mypy surfaces new strict-mode regressions caused by the version bump, fix them in this same step. Do not proceed if any check fails.
>
> Commit message: `Bump mypy floor to 1.13.0 and add [typecheck] extra (#182)`.
