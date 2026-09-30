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

## Round 6 — 2026-09-30
**Findings**:
- step_2 — medium — env move also changes launch mode: a bare console script is not treated as a Python command by the subprocess runner (piped stdout, `PYTHONUTF8=1`), which touches isort's "Windows, piped stdout" limitation
- step_4 — low — check-mode ` --> ` parser splits at the first `:`, breaking absolute Windows paths
- Design — keep or drop "(isort on Windows with piped stdout)" wording in `_unparsable_block`
**Decisions**:
- Launch mode: accept, verified by probe before editing
- ` --> ` parser: accept — same anchor as the stderr regex
- Wording question: resolved by fact rather than asked — the probe shows it
**User decisions**: none
**Changes**: step_2, step_4, step_6, summary.md, Decisions.md. Probe (Windows; `python -m`, `python -m` without `PYTHONUTF8`, console script): identical behaviour in every mode, so no regression. isort `--check-only` skips a non-ASCII file with a `'charmap' codec` warning in *all* modes, so the old "piped stdout" cause was wrong; isort never flags syntax errors. `_unparsable_block` now reads "The formatter could not parse these files."; `_ARROW_PATH` regex plus test 7c.
**Pre-existing, out of scope**: isort `--check-only` on Windows silently skips non-ASCII files (`charmap`), independent of this issue.
**Status**: committed

## Round 7 — 2026-09-30
**Findings**:
- step_8 — medium — done-when grep criterion unachievable: correct lines in neither list (`CONTRIBUTING.md:252`, `.claude/CLAUDE.md:3`, `project_config.py:162`, `test_formatter_tools.py:269`)
- step_7 — medium — churn-test pseudocode: `dict_keys == list` is always False; keyword before positional arguments is a syntax error
- step_2 — low — missing-binary message needs `bin_dir` when `environment is None`
- step_5 — low — prefix/target "overlap" undefined; `startswith` gives false notices
- step_3 — low — intro promises helpers the step doesn't specify
- Design — in write mode a syntax error in `ruff_imports` stops the run, so `ruff_format` never formats the other files (black repos keep going)
**Decisions**:
- All five defects: accept
- Fail-fast: ask user
**User decisions**:
- Q3: B — keep going when the only failure is unparsable files
- isort non-ASCII `--check-only` skip: do not open an issue
**Changes**: step_2–step_5, step_6, step_7, step_8, summary.md, Decisions.md. Step 8 do-not-change table completed from an actual grep run (README 198/205 also got enumeration edits); churn test fixed; runner resolves `env` once; per-file-ignores compared by path component (test 9c); step 3 intro reworded. The engineer first implemented B with a new `FormatterResult.only_unparsable` field and per-runner rules. The supervisor replaced that with the simpler loop rule `if not success and not unparsable_files: break`: no new field (the issue avoids mcp_coder-visible `FormatterResult` changes), and steps are independent and idempotent. Early returns now guarantee empty `unparsable_files` (a gap in `ruff_imports` fix-run returns was closed). Named regression exception: black now runs after isort reports unparsable files.
**Status**: committed

## Round 8 — 2026-09-30
**Findings**:
- step_5 — low — "every mocked syntax-error diagnostic uses `invalid-syntax`" contradicts test 6's `null` repeat
- step_6 — low — "five cases" vs a six-row table
- Design — medium — console scripts are only found in the interpreter's own directory; black/isort inherit ruff's limitation (`pip install --user`, conda layouts)
- Design — low — release note misses CI version drift for projects pinning their own black/isort
**Decisions**:
- Both wording defects: accept
- Script lookup: accept as a documented known limitation in `docs/upgrade-notes.md`; no fallback, since the issue decided one rule for all four steps. Docs only, no scope change, so not escalated.
- CI drift: accept — one line in the upgrade note, mirroring `README.md:152`
**User decisions**: none
**Changes**: step_5, step_6, step_8, summary.md, Decisions.md.
**Status**: committed

## Round 9 — 2026-09-30
**Findings**:
- step_4 — medium — `ruff format --check` text parser relies on the default `full` output; project `output-format = "concise"` or `RUFF_OUTPUT_FORMAT` would silently break it
- Design (simplification) — use `--output-format json` in check mode and reuse `parse_ruff_json_output`, dropping the marker parser
- step_5 — low — `fix.stdout + fix.stderr` duplicates step 3's `combine_output`
**Decisions**:
- Output format: accept — resolved by probe before choosing
- JSON simplification: supervisor decision after probe (smaller code, consistent with `ruff_imports`, and also closes the output-format gap); not escalated
- `combine_output`: accept
**User decisions**: none
**Changes**: step_4, step_5, summary.md, Decisions.md. Probe (ruff 0.16.9): JSON check output gives `code == "unformatted"` / `"invalid-syntax"` with one entry per affected file, parsed correctly by `parse_ruff_json_output`; concise config/env breaks the text markers; an explicit `--output-format` flag wins over config/env. Check mode now uses JSON; `_is_syntax_error` and `_render_diagnostics` are defined once in `ruff_runner.py` and shared with step 5; `_ARROW_PATH` and the marker parser are removed; write-mode `_FAILED_TO_PARSE` kept.
**Status**: committed

## Round 10 — 2026-09-30
**Triage rules changed (user direction)**: from this round, ignore line numbers, counts, wording and cross-reference drift unless it would mislead the implementer; a round with no high/medium findings counts as done; low findings are logged, not actioned.
**Findings**:
- step_8 — medium — release note misses step 6's breaking changes (no-declaration error, `steps=[]` error, `DEFAULT_STEPS` removed)
- step_6 — medium — user-visible MCP tool docstring stays wrong until step 8
- summary — low — CI's `pycycle` not in per-step checks
- step_2 — low — `formatter_binary`'s `environment=None` default unused
- Design — `--no-deps` installs don't enforce the ruff floor; mcp_coder pins `ruff>=0.9.0`
- Design — optionally split step 3
**Decisions**:
- Release note: accept
- Docstring to step 6: accept
- pycycle, `formatter_binary` default: skip (low, logged for the implementer)
- `--no-deps` floor: out of scope — belongs to the mcp_coder#1173 follow-up (raise mcp_coder's ruff floor when it selects the ruff steps); told the user
- Split step 3: skip (bundling is justified in the plan)
**User decisions**: none
**Changes**: step_6, step_8, summary.md, Decisions.md.
**Status**: committed

## Round 11 — 2026-09-30
Reviewer prompt tightened: only wrong behaviour, tests that can't pass, unsatisfiable checks, missing requirements, contradictions about what to build.
**Findings**:
- step_5 — medium — `ruff_imports` JSON run lacks `--no-fix`; with `[tool.ruff] fix = true` check mode rewrites files and write mode's pre-check returns empty `files_changed`
**Decisions**:
- `--no-fix`: accept, after a probe confirmed it (with `fix = true`, the JSON run sorted the file and reported nothing, exit 0; with `--no-fix` the file was untouched and `I001` reported, exit 1). Step 4's `format --check` is unaffected (confirmed).
- summary.md's asymmetry table still shows the command without `--no-fix`: skipped — step 5 is authoritative (drift rule)
- Out of scope: `run_ruff_fix_impl` has the same gap
**User decisions**: none
**Changes**: step_5 (argv, algorithm, prompt, tests 1/1b/2), Decisions.md.
**Status**: committed

## Round 12 — 2026-09-30
**Findings**: none (tight reviewer prompt)
**Decisions**: —
**User decisions**: none
**Changes**: none
**Status**: no changes needed

## Final Status
Converged after 12 rounds (11 plan commits in this run, plus this log commit). No high findings since round 2; round 12 found nothing that would lead to a wrong build.

User decisions this run: formatter version via a `--version` subprocess per step; ruff floor raised to `>=0.16.8` (committed in `pyproject.toml`); continue past steps that report unparsable files; no issue for the pre-existing isort `--check-only` non-ASCII skip.

Out of scope, noted: `run_ruff_fix_impl` lacks `--no-fix` on its pre-check; the mcp_coder#1173 follow-up should raise mcp_coder's ruff floor when it selects the ruff steps.

Plan is ready for approval.
