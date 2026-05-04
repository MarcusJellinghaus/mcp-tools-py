# Implementation Review Log — Issue #171

Goal: structured output for `run_lint_imports_check` so contract failures
surface even when MCP transport truncates output.

Branch: `171-run-lint-imports-check-hides-failures-return-code-dropped-output-unstructured`

## Round 1 — 2026-05-04

**Findings**:
- No Critical findings.
- No Accept findings.
- Skip 1 — `runners.py` raw body duplicates the `Contracts:` summary line under the structured header.
- Skip 2 — `_strip_verbose_flags` filters exact `-v` / `--verbose` tokens only; combined `-vv` etc. not stripped.
- Skip 3 — no explicit test that a malformed warning (no terminating `.` even after wrapping) is silently dropped.
- Quality checks: `pylint` PASS, `pytest` (`-n auto -m "not integration"`) PASS (529 passed / 1 skipped), `mypy` PASS.
- Bonus live verification: `run_lint_imports_check` against this branch returns `=== PASSED ===` on line 1; `run_tach_check` clean.
- Design conformance: state header on top, three-state classifier matches truth table, `--verbose`/`-v` stripped with info line, `MAX_OUTPUT_LINES = 300` redeclared locally, ERROR-fallback also capped, old helper + regexes + `re` import removed cleanly, `.importlinter` and `tach.toml` self-registered.

**Decisions**:
- Skip 1: intentional per `summary.md` §4 (full raw stdout under structured header is the design).
- Skip 2: out of design scope; `_strip_verbose_flags` matches exact tokens by intent. Speculative.
- Skip 3: regex non-match handles malformed-warning case correctly by construction; belt-and-braces only.

**Changes**: none — no Critical/Accept findings.

**Status**: no code changes needed; loop terminates after one round.

## Final Status

- Rounds run: 1
- Code changes: none (all findings Skip-bucket).
- Quality checks: pylint, pytest (`-n auto -m "not integration"`, 529 passed / 1 skipped), mypy — all green.
- Supervisor checks: vulture clean, lint-imports `=== PASSED ===` (3 kept, 0 broken).
- Verdict: ready to ship.

