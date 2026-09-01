# review-plan review log 1

## Round 1 — 2026-09-01
**Findings**:
I'll gather context first.Now let me verify the plan's claims against the actual repo files.`pr_info/steps/step_1.md:263` — high — Verification 2 asserts `search_files(pattern="format_all")` returns nothing outside `pr_info/`; `CONTRIBUTING.md:106,224,252,274` reference `tools\format_all.bat`, so this gate cannot pass as written.
`pr_info/steps/step_1.md:97` — medium — `CONTRIBUTING.md` names the same nonexistent `tools\format_all.bat` as the formatting entry point; the plan neither corrects it nor lists it under the summary's explicit exclusions, so the repo still contradicts the corrected `architecture.md:58`.
`pr_info/steps/step_1.md:11` — medium — Edit list covers §1, 2, 3, 5, 6 but not §4 `architecture.md:99` ("Each tool follows `models`/`parsers`/`reporting`/`runners` structure"), which directly contradicts new Edit 10 text stating `vulture`, `tach`, `lint_imports` are `runners.py` alone.
`pr_info/steps/step_2.md:13` — medium — `README.md:47` ("all checker tools (pylint, mypy, vulture)") is the same 3-of-N inventory drift the issue targets; `resolve_target_directories` is also used by `ruff_check_tool`, `ruff_fix_tool`, `bandit_tool` and `formatter_tools`, and the step leaves the line untouched.
`pr_info/steps/step_1.md:89` — low — Replacement Development line lists `mcp-coder`, which is absent from `[project.optional-dependencies].dev` (`mcp-workspace`, `pycycle`, `pydeps` only).
`pr_info/steps/step_1.md:87` — low — Replacement Runtime line is presented as mirroring `[project.dependencies]` but omits `pathspec`, `igittigitt` and `pytest-asyncio`.
`pr_info/steps/step_1.md:179` — low — New dependency rule "Registrars depend on the `code_checker_*` packages" holds only for `checker_tools`; `formatter`, `refactoring`, `utility_tools` and `inspect_library` depend on none.
`pr_info/steps/step_1.md:68` — low — "Nine checkers" is followed by eight names; the count reconciles only if "ruff (check and fix)" is read as two.
`pr_info/steps/step_2.md:79` — low — "The sections below document the parameters of the most-used ones" mischaracterizes `### Pylint Configuration` and `### Target Directory Auto-Detection`, which also nest under `## Features` and are not parameter docs.
**Decisions**:
Verdict(decision='tasks', tasks=["step_1.md:263 — Fix Verification 2: either update CONTRIBUTING.md's `tools\\format_all.bat` references (lines 106, 224, 252, 274) as part of the change, or narrow the verification gate so it does not assert zero `format_all` hits repo-wide.", "step_1.md:97 — Bring CONTRIBUTING.md's formatting entry point in line with the corrected architecture.md:58, or explicitly list CONTRIBUTING.md under the summary's stated exclusions with a reason.", 'step_1.md:11 — Add an edit for architecture.md §4 (line 99, "Each tool follows models/parsers/reporting/runners structure"), which contradicts new Edit 10 stating vulture, tach and lint_imports are runners.py only.', 'step_2.md:13 — Update README.md:47 ("all checker tools (pylint, mypy, vulture)") to reflect that resolve_target_directories is also used by ruff_check_tool, ruff_fix_tool, bandit_tool and formatter_tools.', 'step_1.md:89 — Remove `mcp-coder` from the replacement Development dependencies line; [project.optional-dependencies].dev lists only mcp-workspace, pycycle and pydeps.', 'step_1.md:87 — Add `pathspec`, `igittigitt` and `pytest-asyncio` to the replacement Runtime dependencies line, or drop the claim that it mirrors [project.dependencies].', 'step_1.md:179 — Restate the new dependency rule so it is true: only checker_tools registrars depend on the code_checker_* packages; formatter, refactoring, utility_tools and inspect_library do not.', 'step_1.md:68 — Reconcile the "Nine checkers" count with the eight names listed (either list nine names or state the count as eight with ruff covering check and fix).'], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-09-01
**Findings**:
I'll gather context: knowledge base, the issue chain, and the plan files.`pr_info/steps/step_1.md:262` — high — Replacement text "Only pytest parses a JSON report file; the others parse stdout directly" is false: `code_checker_bandit/runners.py:57-98` writes bandit JSON to a temp file and reads it back (the `-f json -o <path>` path added in #211). The edit introduces a new inaccuracy into the document it is correcting.
`pr_info/steps/step_2.md:13` — high — Step scope names only three stale README inventories (`:9-11`, `:19`, `:25-27`); `README.md:104-105`, `:129`, `:151` and `:171` also state that the venv must contain "pytest, pylint, and mypy" only, while `server.py:_check_tool_availability` probes `lint-imports`, `vulture`, `ruff`, `bandit` and `tach` binaries in the same venv. Neither fixed nor listed under the summary's exclusions, so the corrected README still gives incomplete setup guidance.
`pr_info/steps/step_2.md:79` — medium — Replacement Features text directs readers to the parameter tables, which are themselves stale: `README.md:68` documents a `verbosity` parameter that `run_pytest_check` does not accept (`checker_tools/pytest_tool.py:23-27`); the pylint table omits `max_issues` and the mypy table omits `cache_dir`.
`pr_info/steps/summary.md:83` — low — `pyproject.toml` is listed as not modified without noting that its `description` ("An MCP server for running python code checks (pylint, pytest and mypy)") carries the same 3-of-17 inventory drift the issue targets.
**Decisions**:
Verdict(decision='tasks', tasks=['step_1.md:262 — Correct the replacement sentence: bandit also writes and reads a JSON report file (code_checker_bandit/runners.py:57-98, `-f json -o <path>`), so the claim that only pytest parses a JSON report file is wrong. Restate it to cover both pytest and bandit.', 'step_2.md:13 — Extend the step to fix the venv-contents claims at README.md:104-105, :129, :151 and :171 ("pytest, pylint, and mypy") so they match the binaries server.py:_check_tool_availability probes (lint-imports, vulture, ruff, bandit, tach), or explicitly list those lines under the summary\'s exclusions with a reason.', 'step_2.md:79 — Fix the parameter tables the replacement Features text points at: remove the nonexistent `verbosity` parameter for run_pytest_check (README.md:68; see checker_tools/pytest_tool.py:23-27), add `max_issues` to the pylint table, and add `cache_dir` to the mypy table.'], escalate_reason=None)
**Changes**:
applied

## Round 3 — 2026-09-01
**Findings**:
I'll gather context: knowledge base, the issue and its links, and the plan files.`docs/architecture/architecture.md:213` — low — Step 1 leaves "Optional: `--venv-path` to use a specific virtual environment for tool execution" untouched while Step 2 (`pr_info/steps/step_2.md:118`) rewrites the README to state `--venv-path` is required for ruff, bandit, vulture, tach and lint-imports to be found at all; the two corrected documents disagree on that point.
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
dismiss
