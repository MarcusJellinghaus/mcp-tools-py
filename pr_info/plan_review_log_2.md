# review-plan review log 2

Continuation of `plan_review_log_1.md`, which hit the automated 5-round limit
without converging (issue #233 comment, 2026-09-26T19:29:55Z: "Automated
review-plan review reached the round limit (5 rounds) without converging —
handing off for human review"). Started fresh under human/supervisor
triage. Known unresolved items carried over from log 1, each raised multiple
times but never selected for fixing by the automated single-task verdicts:

- `step_3.md:1` (3 occurrences) — step 3 is oversized for one TDD commit.
- `step_2.md:116`/`:153` (3 occurrences) — `tests/test_target_scripts_contract.py`
  does not actually verify step 2's new `probe.py locate` code; it builds a
  synthetic fake package and never reads the real `probe.py`.
- `step_1.md:91`/`:93` (2 occurrences) — the post-step-1 `unavailable_message`
  for lint-imports blames "install incomplete, reinstall mcp-tools-py" in the
  issue's own scenario (tool env has import-linter, project venv doesn't),
  which is not true — the directory it names does contain the script.

## Round 1 — 2026-09-26
**Findings**: Engineer subagent confirmed all three carried-over items as
still present and real (not resolved, not false positives), plus one
additional low finding:
- Step 3 still bundles the pure config/PYTHONPATH helpers, the
  `_format_report` refactor, and the tool-env wiring in one commit; a split
  (pure helpers + refactor first, wiring second) is feasible without ever
  leaving lint-imports resolving from the tool env without its bridge.
- Step 2's VERIFY claim that `tests/test_target_scripts_contract.py` proves
  the stdlib-only contract for the new `probe.py locate` code is factually
  wrong — that test fabricates a synthetic package/`probe.py` and never
  touches the real file.
- Step 1's lint-imports `unavailable_message`, in the issue's own normal
  scenario (tool env has the script, project venv doesn't), falsely claims
  mcp-tools-py's install is incomplete — `is_tool_available` reads
  `tool_environment` (True) while the handler's binary lookup still reads
  `environment` (None), so the short-circuit fires with a message naming a
  directory that does have the script.
- Low: `environment_info.py`'s module docstring claims everything is cached
  per interpreter; step 2 adds an explicitly uncached `locate_packages`
  without noting the exception.
**Decisions**: All four accepted as straightforward plan-structure/accuracy
fixes — none affect scope or architecture, so no user escalation needed.
Instructed the engineer to apply all four in one `/plan_update` pass (rather
than one per round, which is how log 1 hit its round limit without
converging).
**Changes**: Applied via `/plan_update`:
- Step 3 split into two: new `step_3.md` (pure helpers +
  `info_line`→`info_lines` refactor, no environment switch) and new
  `step_4.md` (locate_packages wiring, PYTHONPATH, registrar switch,
  `.importlinter` cleanup, docstring fix, `test_bridge_integration.py`). Old
  `step_4.md` (docs) renamed `step_5.md`. `summary.md` updated to match.
  New `pr_info/steps/Decisions.md` added logging these decisions.
- Step 2's VERIFY section corrected: stdlib-only compliance now justified by
  code inspection + the existing real-subprocess `TestProbeScript` test,
  not the unrelated contract-test file.
- Step 1: lint-imports carved out of the tool-env-routed
  `is_tool_available`/`unavailable_message`/`_warn_missing_console_scripts`
  set — it keeps reading `environment` (binary, answer, and message all
  agree) until step 4 moves all three together.
- Step 2: added a one-sentence docstring caveat that `locate_packages` is
  deliberately uncached.
**Status**: committed (see commit agent run)
