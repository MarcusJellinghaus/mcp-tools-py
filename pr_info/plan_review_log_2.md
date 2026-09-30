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
