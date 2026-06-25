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

## Round 2 — 2026-06-25

**Findings** (from fresh `/plan_review` after Round 1 edits):
- No BLOCKERs. Re-verified all load-bearing claims against current code: bandit `runners.py` stdout-parse + error short-circuits; `parsers.py` empty-input → silent "no issues" (guard genuinely necessary, correctly placed before the parser); the mirrored pytest `mkdtemp`/`shutil.rmtree` pattern; rope `create_move` patch seams at lines 751/356 with dry-run dest created before the `try` (cleanup assertions valid); `sample_project` fixture contents.
- All four Round-1 clarifications confirmed present and internally consistent (guard-test legibility assert; enumerated `test_build_command_*` rewrites; `os.path.isdir` `return_value` note; intentional hint-string divergence).
- Remaining items are cosmetic NITPICKs only, explicitly non-gating: (a) one-line confirmation that `bandit_tool.py` surfaces `error` regardless of `return_code` (the existing `return_code > 1` path already proves the surfacing exists); (b) guard test could cover both missing-file and empty-file sub-cases (single case satisfies the `not exists or getsize==0` guard); (c) summary's longer pytest marker-exclusion list is a harmless no-op vs CLAUDE.md's single `integration` marker.

**Decisions**: No changes applied — all findings are cosmetic and non-gating per the reviewer. No design/requirements questions to escalate.

**User decisions**: none required.

**Changes**: None. Zero plan-file changes this round → review loop terminates.

**Status**: no changes needed.

---

## Final Status

**Rounds run:** 2.
**Plan changes:** Round 1 applied four mechanical clarifications (committed `7a62b6d`); Round 2 produced zero changes.
**Outcome:** Plan is **ready for approval / implementation.** No BLOCKERs; every technical precondition (signatures, line numbers, patch seams, fixtures, parser empty-input behavior, mirrored pytest temp-file pattern) verified against the current code on this branch. The plan faithfully honors issue #193's Decisions table (temp-file `-o` bandit capture, empty-file anomaly guard, `isinstance`-based AttributeError hint on both move functions, pytest kept verify-only/non-numbered). Two independent steps → two commits, TDD-first, standard quality gates.
**No user escalations were needed.**
