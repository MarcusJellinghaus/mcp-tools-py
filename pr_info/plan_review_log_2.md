# Plan review log 2 — issue #235

Supervised plan review (`/plan_review_supervisor`). Continues from `plan_review_log_1.md` (5 rounds).

## Round 1 — 2026-09-30
**Findings**:
- step_2 — high — cached `tool_environment()` accessor as `default_factory` breaks `_patched_tool_env`-based tests (`test_server_params.py:795/:819`), order-dependent under xdist
- step_6 — high — six existing `test_formatter_runner.py` tests call `run_format_code` without `steps` against a project with no pyproject.toml; they hit the "neither declared" error
- step_7 — medium — Test 10 doesn't say which `ToolContext`; the conftest fixture's tool env is empty stubs
- step_5 — low — `--fix` run lacks the timed-out / execution-error early return
- pyproject.toml — medium — `ruff>=0.9.0` floor is below 0.16.8, the version the output formats were verified against
- summary/step_3 — design — version via package metadata deviates from the issue's `--version` subprocess
- Repeat check (supervisor): `runner.py::run_format_code` `python_executable` deprecation docstring, raised in log 1 rounds 1–3 and never tasked
**Decisions**:
- Cached accessor: accept (bug)
- Six runner tests: accept (tests would fail)
- Test 10 ToolContext: accept (under-specified)
- `--fix` early return: accept
- ruff floor: ask user
- Version lookup: ask user
- Deprecation docstring (repeat): accept; reviewers raised it three times, and it is required by the issue
**User decisions**:
- Version lookup: B — follow the issue, `<binary> --version` subprocess per step within the step's timeout, "unknown" on failure
- ruff floor: on hold
**Changes**: summary.md, step_2–step_7 updated; new `Decisions.md`. Version via `--version` (`formatter_version(binary, timeout_seconds)` in step 3); accessor dropped, `None` falls back to uncached `PythonEnvironment.resolve()`; six runner tests pass `steps=["isort", "black"]`; Test 10 builds its own `ToolContext`; step 5 `--fix` early return plus test 10b; deprecation docstring stated in step 2.
**Status**: committed

## Round 2 — 2026-09-30
**Findings**:
- step_5 — high — `run_ruff_imports` ignores pre-check exit 2 (e.g. invalid config); empty stdout → check mode reports `success=True`
- pyproject.toml — medium — ruff floor `>=0.9.0` vs formats verified on 0.16.8 (repeat of round 1, raised independently)
- step_5 — medium — unspecified which invocation `output` comes from; check mode would dump raw JSON
- step_1 — low — `move_symbol` leaves `logger`/imports to reconcile; "nothing else remains" check would fail
- step_5 — low (design) — per-file-ignores key with empty literal prefix (`*.py`) undefined
- step_5 — low — wrong line reference (`:45` → `:46`)
- Engineer-raised during fix: unverified assumption that a syntax error doesn't make `ruff check` exit 2
**Decisions**:
- Exit 2: accept (silent false success)
- Output source: accept — write mode uses `--fix` text; check mode renders parsed messages
- step_1 move note: accept
- Empty prefix: supervisor decision — skip as documented false negative, consistent with the summary's literal-matching rule
- Line ref: accept
- ruff floor: repeat of round 1 (on hold) — re-asked the user, since an independent reviewer re-raised it with new evidence (`Would reformat:` format in older ruff)
- Unverified assumption: resolve now with a scratch probe rather than defer to implementation
**User decisions**:
- ruff floor: A — raise to `ruff>=0.16.8` now
**Changes**: step_1, step_4, step_5, summary.md, Decisions.md, pyproject.toml. Exit-2 handling plus tests 7b/7c; output source plus test 7d; step 1 move checks; empty-prefix skip plus test 9a; `:46`. Floor raised. Probe on ruff 0.16.9: syntax errors carry `code: "invalid-syntax"`, not null — step 5's predicate became `not m.code or m.code == "invalid-syntax"` (would otherwise have misclassified broken files and failed step 7 test 6a). Exit codes and `--check` markers confirmed.
**Status**: committed

## Round 3 — 2026-09-30
**Findings**:
- step_3 — medium — `test_run_black_truncates_output` / `test_run_isort_truncates_output` break (banner makes it "51 more lines"); plan says leave existing tests alone
- summary/all steps — medium — CI runs `ruff check` and `vulture`; plan never does. Unused `python_executable` and new autouse fixtures would fail vulture
- step_2 — medium — instance `patch.object` on frozen `PythonEnvironment` raises `FrozenInstanceError`
- step_8 — low — README :150, :152, :204 missing from the sweep; grep is case-sensitive
- step_6 — low — inaccurate "runner resolves again" sentence
- Design — low — drop per-file-ignores prefix matching and report any `I` entry
**Decisions**:
- Truncation tests: accept
- ruff/vulture in done criteria plus whitelist plan: accept
- Frozen dataclass: accept — delete the stub file instead
- README lines: accept
- step_6 sentence: accept
- Drop prefix matching: skip — the issue's Decisions table requires reporting the *covered directories*; "any `I` entry" would not name them
**User decisions**: none
**Changes**: summary.md, Decisions.md, step_1–step_8. Truncation tests updated to "51 more lines"; `run_ruff_check`/`run_vulture_check` added to every DONE WHEN; whitelist entries `python_executable` (step 2), `_fixed_version_line` (step 3), `_declare_formatter` (step 6), verified by vulture probe; `test_tool_unavailable_returns_error` deletes the black stub; README :150/:152/:204 and `main.py:74` added to step 8, with case-insensitive greps; step_6 sentence replaced. Engineer flagged that step 8's "deliberate survivors" wording looked confusing; supervisor left it, since the "five registrars" hits are meant to survive.
**Status**: committed

## Round 4 — 2026-09-30
**Findings**:
- step_2 — medium — existing black/isort runner tests don't mock binary lookup; they fail on an interpreter without the scripts
- step_8 — low — contradictory "survivors" counts in the grep expectations (**repeat of round 3**, an engineer's note)
- step_8 — low — architecture.md `utils/` list, `project_config.py` bullet, `formatter/` bullet not updated
- step_4 — low — "path before `:<line>`" breaks on drive-letter paths; name the regex
- step_6 — low — `resolve_steps` returns module-level lists; a caller could mutate them
- step_7 — low — churn test fixture should use stdlib-only imports
- step_1 — low (optional) — `ImportError` test guards a decision, not behaviour
**Decisions**:
- Binary lookup fixture: accept
- Survivor counts: accept — repeat. In round 3 the supervisor dismissed it, reasoning that the "five registrars" lines were the survivors. An independent reviewer showed the grep can't match those lines, so the round-3 reason was wrong.
- architecture.md lines: accept
- Regex: accept
- Copies from `resolve_steps`: skip — speculative (only matters if a caller mutates the result)
- Stdlib-only fixture: accept
- `ImportError` test: accept dropping — tests a decision, not behaviour
**User decisions**: none
**Changes**: step_1, step_2, step_3, step_4, step_5, step_7, step_8, summary.md, Decisions.md. `_fixed_formatter_binary` autouse fixture (whitelisted; steps 4/5 aligned, with real-lookup overrides where needed); step 8 grep criterion rewritten; architecture.md utils/formatter bullets added; `_FAILED_TO_PARSE` regex plus test 7b (probed); churn fixture stdlib-only; step 1 `ImportError` test dropped.
**Status**: committed

## Round 5 — 2026-09-30
**Findings**:
- step_5 — medium — per-file-ignores notice matches any code starting with `I` (`INP001`, `ICN`, `ISC`, `INT`), causing false alarms
- step_6 — low — `test_invalid_step_raises_valueerror` pattern `"ruff"` will match the valid-steps list
- step_8/summary — low — `README.md:44` names no formatter; nothing to edit
- step_1 — low — `utils/ruff_parsing.py` needs a module docstring (ruff `D` rules)
- step_5 — low — `extend-per-file-ignores` not read
- Design — `--fix` pass could be skipped when the pre-check finds nothing fixable
**Decisions**:
- Code matching: accept — `"ALL"` or `^I\d*$`, plus an `INP001` no-notice test
- Invalid-step test: accept
- README:44: accept as "verified, no edit" (the issue lists it, so keep a note)
- Module docstring: accept
- `extend-per-file-ignores`: accept as a documented known false negative (no extra reading), consistent with the literal-matching simplification
- Skip `--fix`: skip — optimisation only; the plan follows the issue's two-invocation design
**User decisions**: none
**Changes**: step_1, step_5, step_6, step_8, summary.md, Decisions.md.
**Status**: committed
