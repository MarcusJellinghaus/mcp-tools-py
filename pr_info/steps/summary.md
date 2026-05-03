# Issue #187 — Pytest `run_tests` swallows pytest output across error paths

## Problem

`run_tests` in `src/mcp_tools_py/code_checker_pytest/runners.py` `print()`s pytest's actual stdout/stderr to the MCP server's stdout in **every** error / fallback branch — invisible to the LLM client. For exit codes **3** (internal error), **4** (usage error), and **>5** (plugin error), it then raises a generic `RuntimeError` / `ValueError` containing only canned `"Suggestion: …"` text, so LLM clients see no diagnostic information and the failure is undebuggable from the client side.

## Fix (single commit, single step)

In `src/mcp_tools_py/code_checker_pytest/runners.py`, replace every `print()` call site inside `run_tests` with the appropriate logger call (`logger.warning(...)` for sites that dump real pytest output / failure diagnostics, `logger.debug(...)` for operational status chatter) so output is visible via standard log inspection instead of being dumped to stdout — and drop the tautological line-309 print entirely. **Additionally, every error path that raises must surface the real pytest stdout/stderr to the LLM caller through the raised exception text** — the MCP caller path is `{"success": False, "error": str(e)}`, so only what's in the exception message reaches the LLM client. Operator-side logging alone is not enough.

The branches touched (verified by review against current source):

| Approx. line | Site | Change | Log level |
|--------------|------|--------|-----------|
| ~210 | `print(f"Running command: ...")` (debug echo) | `print` → `logger.debug` | `debug` |
| ~217 | `raise RuntimeError(subprocess_result.execution_error)` | append `_build_error_detail(subprocess_result.stdout, subprocess_result.stderr)` to `RuntimeError` (verified: `execution_error` is a separate string field on `CommandResult` — does not contain stdout/stderr) | n/a (raise) |
| ~221 | `print(f"Command completed with return code: ...")` (debug echo) | `print` → `logger.debug` | `debug` |
| ~223 (raise) | `raise TimeoutError(f"Subprocess timed out: ...")` | append `_build_error_detail(subprocess_result.stdout, subprocess_result.stderr)` to `TimeoutError` (subprocess_runner captures any partial stdout/stderr on the same `CommandResult` before timing out) | n/a (raise) |
| ~230 | `print(f"Command timed out after ...")` (real failure path, fired right before raising the line-223 `TimeoutError`) | `print` → `logger.warning` | `warning` |
| ~247 | `print("pytest-json-report plugin not found, attempting to install it...")` (operational status) | `print` → `logger.debug` | `debug` |
| 271 | `pytest-json-report` install failure | `print` → `logger.warning` **and** append `_build_error_detail(install_result.stdout, install_result.stderr)` to `RuntimeError` | `warning` |
| ~278 | `print("Installed pytest-json-report, retrying...")` (operational status) | `print` → `logger.debug` | `debug` |
| 289 | retry timed out | `print` → `logger.warning` **and** append `_build_error_detail(retry_result.stdout, retry_result.stderr)` to `TimeoutError` | `warning` |
| 304 | install / retry error handler | `print` → `logger.warning` | `warning` |
| 309 | tautological log on no-tests-found path | **deleted entirely** — the `raise ValueError(...)` on the next line already explains itself, and `_build_error_detail(...)` is already appended to the raised `ValueError` (line 311). No conversion needed. | n/a |
| 337 | `returncode == 3` (internal error) | `print` → `logger.warning` **and** append `_build_error_detail(...)` to exception, drop canned `Suggestion:` text and dead `error_context` ternaries | `warning` |
| 343 | `returncode == 4` (usage error) | same as above | `warning` |
| 355 | `returncode > 5` (plugin error) | same as above | `warning` |
| ~363 | `print(combined_output)` in the no-report-file fallback (this print and the line-384 `raise RuntimeError(base_msg)` are the **same** branch — the print dumps swallowed pytest output right before the raise) | `print` → `logger.warning` (it's swallowed pytest output, not operational debug) | `warning` |
| 384 | no-report-file `RuntimeError` (currently includes stderr only) | extend `base_msg` to use `_build_error_detail(output, error_output)` so stdout is also included | n/a (raise) |
| 416–418 | outer error handler | `print` → `logger.warning` | `warning` |

**Principle (state explicitly):**
1. **Pytest-output prints become `logger.warning(...)`** — anything that dumps `combined_output` / pytest stderr / pytest stdout must be visible to operators at WARNING level (these are real failure diagnostics, not chatter).
2. **Operational/debug prints become `logger.debug(...)`** — command-echo, "attempting to install", "installed, retrying", "completed with return code" are status chatter and belong at DEBUG.
3. **Every error path that raises must surface real stdout/stderr to the LLM caller** (via the raised exception text), not just to the operator log. The pattern is `_build_error_detail(stdout, stderr)` appended to the exception message — already correct at line 311 and (after this fix) at lines 217, 223, 271, 289, 337, 343, 355, 384.

Resulting message shape for the three returncode-based branches:

```
Internal Error: <exit_code_meaning>. stderr: <…> stdout: <…>
Usage Error:    <exit_code_meaning>. stderr: <…> stdout: <…>
Plugin Error:   <exit_code_meaning>. stderr: <…> stdout: <…>
```

The early-raise paths (217 `RuntimeError(execution_error)`, 223 `TimeoutError`), install-failure (271), retry-timeout (289), and no-report (384) branches gain the same trailing ` stderr: … stdout: …` snippet via inline `_build_error_detail(...)` calls (no new helper / abstraction — match the existing line-311 pattern). Final raising-path set: 217, 223, 271, 289, 337, 343, 355, 384.

## Architectural / design notes

- **No new abstractions.** Reuses the existing `_build_error_detail()` helper (lines 26–41), the existing `truncate_stderr()` defaults, and the already-bound module-level `logger`. The `returncode == 5` branch is the reference implementation for the snippet shape — the three error branches now match its style.
- **Three exit-code branches kept inline.** A `{returncode → (label, exception_cls)}` table was considered and rejected: 3 near-identical 3-line branches is below the threshold where a helper pays off (KISS).
- **Logger over `print` everywhere in `run_tests`.** Failure-diagnostic prints become `logger.warning(...)`, operational/status prints become `logger.debug(...)`. Aligns with the rest of the module (existing `logger.warning` calls at lines 329–333, 350–352, and existing `logger.debug` at line 187). Operators retain server-side visibility through standard log inspection; nothing leaks onto the MCP server's stdout.
- **Scope is `run_tests` only.** Other checker runners (pylint, mypy, ruff, vulture, bandit, tach, lint-imports) may have the same swallowed-output pattern — explicitly **out of scope** for this PR; file follow-up issues if found. No scope creep beyond `run_tests`.

## Folders / modules / files

### Modified
- `src/mcp_tools_py/code_checker_pytest/runners.py` — every `print()` in `run_tests` is removed: pytest-output prints (~230 timeout-warning, 271 install-fail, 289 retry-timeout, 304 install/retry handler, ~363 no-report dump, 416–418 outer handler) become `logger.warning(...)`; operational/debug prints (~210 command echo, ~221 return-code echo, ~247 plugin-not-found, ~278 installed-retrying) become `logger.debug(...)`; the tautological line-309 `print("No tests found, raising specific exception")` is **deleted** (the `raise ValueError(...)` is self-explanatory). Eight raising paths (217, 223, 271, 289, 337, 343, 355, 384) additionally gain inline `_build_error_detail(...)` snippets in their raised exception messages so the LLM caller sees real pytest stdout/stderr.
- `tests/test_code_checker/test_runners.py` — new parametrized unit test(s) asserting both the raised exception text (covers all eight error paths: 217, 223, 271, 289, 337, 343, 355, 384) and a `WARNING`-level log record where applicable (uses `caplog`). Split into two parametrized families if mock setup diverges enough between install/timeout vs returncode branches that one parametrize gets ugly — engineer's call, prefer fewer tests.

### Created
- None.

### Deleted
- None.

## Plan

| Step | Description | Commit |
|------|-------------|--------|
| 1 | TDD fix: replace every `print()` in `run_tests` with `logger.warning(...)` (pytest-output sites) or `logger.debug(...)` (operational sites), drop the tautological line-309 print, and surface pytest stdout/stderr in raised exceptions for all eight raising paths (217 execution-error, 223 timeout, 271 install fail, 289 retry timeout, 337/343/355 exit codes 3/4/>5, 384 no-report fallback) | One commit |

A single-commit fix: all branches share the same bug pattern (swallowed output via `print`) and the same fix shape (logger + `_build_error_detail` for raises). Splitting per-branch would mean many near-identical commits with no isolated value per commit.
