# Plan Review Log — Issue #193

**Branch:** `193-macos-run-bandit-check-json-parse-failure-real-bug-pytest-verify-move-module-move-symbol-message-hardening`
**Supervisor run:** 1
**Date:** 2026-06-25

Issue #193 bundles three items: (1) bandit temp-file JSON capture (real bug,
Step 1), (2) pytest verify-only (no code change), (3) move_module/move_symbol
AttributeError hint hardening (Step 2). Plan is fresh — no steps implemented yet.
Branch is up to date with `main` (no rebase needed).

---

## Round 1 — 2026-06-25

**Findings** (from `/plan_review`):
- No BLOCKERs. Engineer verified every load-bearing plan claim against current `main` code — signatures, line locations (rope handlers :407/:789), the pytest `--json-report-file` pattern being mirrored, the parser's silent-empty behavior motivating the guard, and the `rope.refactor.move.create_move` patch seam all hold.
- NITPICK (Step 1): `test_empty_output_file_is_error` only asserted error non-empty — should assert a legible message.
- NITPICK (Step 1): build-command test rewrites under-enumerated (extra-args + multi-dir variants).
- NITPICK (Step 1): `os.path.isdir` patch must stay `return_value`, not blanket `side_effect`, or the guard is masked.
- IMPROVEMENT (Step 2): two hint strings intentionally differ — should be documented so they aren't DRY-collapsed.
- Confirmed correct: pytest Item 2 correctly excluded as a non-step verify-only gate; two-step/two-commit granularity; KISS single-handler approach for Step 2.

**Decisions**:
- Accept & apply the four mechanical clarifications above (improve robustness, no scope/architecture change).
- Skip: Step 2 cleanup assertion (verified, holds); pytest non-step (correctly excluded).
- No design/requirements questions to escalate to the user — plan faithfully honors the issue's Decisions table.

**User decisions**: none required this round.

**Changes**: Applied via `/plan_update` to `step_1.md` (guard-test legibility assert; enumerate all `test_build_command_*` rewrites; `isdir` patch note) and `step_2.md` (note the intentional hint-string divergence). `summary.md` untouched; no code changed.

**Status**: committed (see commit agent).
