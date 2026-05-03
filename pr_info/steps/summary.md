# Issue #187 — Pytest exit codes 3/4/>5 swallow pytest output

## Problem

When pytest exits with code **3** (internal error), **4** (usage error), or **>5** (plugin error), `run_tests` in `src/mcp_tools_py/code_checker_pytest/runners.py`:

1. `print()`s pytest's actual stdout/stderr to the MCP server's stdout — invisible to the LLM client.
2. Raises a generic `RuntimeError` / `ValueError` containing only canned `"Suggestion: …"` text.

LLM clients see only the canned suggestion with **no diagnostic information**, making the failure undebuggable from the client side.

## Fix

In `src/mcp_tools_py/code_checker_pytest/runners.py`, lines 336–359, three error branches:

- **Replace** `print(combined_output)` → `logger.warning(...)` (server-side visibility, no stdout pollution).
- **Append** `_build_error_detail(output, error_output)` snippet to the exception message (already used for the `returncode == 5` path at lines 308–313).
- **Drop** the canned `Suggestion: …` text — the real stderr/stdout snippet replaces it.
- **Drop** defensive `if error_context else 'fallback'` ternaries — `error_context` is always set when `returncode != 0` (line 317–320), so the fallback branches are dead.

Resulting message shape (all three branches):

```
Internal Error: <exit_code_meaning>. stderr: <…> stdout: <…>
Usage Error:    <exit_code_meaning>. stderr: <…> stdout: <…>
Plugin Error:   <exit_code_meaning>. stderr: <…> stdout: <…>
```

## Architectural / design notes

- **No new abstractions.** Reuses existing `_build_error_detail()` helper (lines 26–41) and existing `truncate_stderr()` defaults. The `returncode == 5` branch is the reference implementation — these three branches now match its style.
- **Three branches kept inline.** A `{returncode → (label, exception_cls)}` table was considered and rejected: 3 near-identical 3-line branches is below the threshold where a helper pays off (KISS).
- **`logger.warning` over `print`.** Aligns with the rest of the module (see existing `logger.warning` calls at lines 329–333, 350–352). Operators retain server-side visibility through standard log inspection.
- **No scope creep.** Other checker runners (pylint, mypy, ruff, vulture, bandit, tach, lint-imports) may have the same swallowed-output pattern — explicitly out of scope; file follow-up issues if found.

## Folders / modules / files

### Modified
- `src/mcp_tools_py/code_checker_pytest/runners.py` — three error branches (returncode 3, 4, >5).
- `tests/test_code_checker/test_runners.py` — one new parametrized unit test.

### Created
- None.

### Deleted
- None.

## Plan

| Step | Description | Commit |
|------|-------------|--------|
| 1 | TDD fix for swallowed pytest stdout/stderr on exit codes 3/4/>5 | One commit |

A single-commit fix: the three branches are coupled (same bug pattern, same fix shape, parametrized test covers all three). Splitting per-returncode would mean three near-identical commits and no isolated value per commit.
