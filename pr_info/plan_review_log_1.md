# review-plan review log 1

## Round 1 — 2026-08-31
**Findings**:
I'll gather context: knowledge base, the issue, and the plan files.`pr_info/steps/step_1.md:290` — high — DONE WHEN contains no check that the parser matches real isort output; the whole fix rests on the unverified assumption that the warning arrives on one line (issue's *Observed behaviour* shows one line, its appendix shows two), and with unit tests only a wrong assumption ships a fix that detects nothing on the only platform where the fault occurs. This repo has 11 live triggering files on a Windows dev machine, so a one-off `run_format_code(steps=["isort"], check_only=True)` after implementation settles it for free and belongs in the exit criteria.

`pr_info/steps/step_1.md:207` — medium — "The full list stays visible below the block as isort's own warnings — that is why the cap is safe" is false in the 124-file case the plan itself cites: `_MAX_LINES = 200` truncates the runner output (constraint at line 281 relies on exactly that truncation), so on a large repo the paths beyond the cap are visible nowhere.

`pr_info/steps/step_1.md:176` — low — the block-rendering pseudocode uses plain strings containing `{step}` / `{len(files)}` placeholders with no `f` prefix; copied literally it renders braces instead of values.

`pr_info/steps/step_1.md:178` — low — `_unparsable_block` takes only `(step, files)` yet hardcodes check-mode wording ("they were NOT checked", "A clean result here does NOT mean CI will pass") while the plan emits it in both modes; in apply mode the text would be wrong.

`pr_info/steps/step_1.md:255` — low — the rendering test calls the private `_format_results` directly, whereas all 17 existing uses of `_make_formatter_result` in that file drive the registered tool via `_capture_run_format_code`; routing the new test the same way costs nothing and additionally covers the block reaching the tool output.
**Decisions**:
Verdict(decision='tasks', tasks=['In pr_info/steps/step_1.md, add to DONE WHEN an explicit verification step: after implementation, run run_format_code(steps=["isort"], check_only=True) against this repo and confirm the parser detects the real isort skip warning (the issue shows the warning on one line in Observed behaviour but on two in the appendix — the exit criteria must confirm which the parser actually handles).', "In pr_info/steps/step_1.md around line 207, drop or correct the claim that the full file list stays visible below the block as isort's own warnings: with _MAX_LINES = 200 the runner output is truncated, so in the cited 124-file case paths beyond the cap appear nowhere. State the cap's real consequence instead of asserting the list is still visible."], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-08-31
**Findings**:
I'll gather context first.`pr_info/steps/step_1.md:297` — high — the real-isort exit criterion is not executable as written: `run_format_code` is served by the already-running `mcp-tools-py` MCP server process, which holds the pre-change code, so the implementer will see no `ERROR: ...` block and, per lines 303-305, conclude "the message is wrapped and the parser needs reworking". The check must exercise the working copy directly (e.g. a `.scratch` probe importing `run_isort` from `src/` against this repo's `src`/`tests`), or state that a server restart is required first.

`pr_info/steps/step_1.md:234` — medium — the fixture's trailing `warn(f"Unable to parse file {file}")` line omits `" due to "`, so it cannot match `_UNPARSABLE_RE` by construction; the real emission the issue describes is `warn(f"Unable to parse file {file} due to {error}")`, which would match and yield a bogus `{file}` path. The test that exists to prove non-matching lines are skipped proves nothing about the line it is modelled on.

`pr_info/steps/step_1.md:176` — low — `_unparsable_block(step, files)` hardcodes check-mode wording ("they were NOT checked", "A clean result here does NOT mean CI will pass") while the block is emitted in both modes; `_format_results` already receives `check_only` (`formatter_tools.py:98`), so passing it through is free. Raised in round 1, not tasked, still open.
**Decisions**:
Verdict(decision='tasks', tasks=["In pr_info/steps/step_1.md around line 297, make the real-isort exit criterion executable against the working copy: the running mcp-tools-py MCP server holds the pre-change code, so calling run_format_code would show no ERROR block and mislead the implementer per lines 303-305. Replace it with a .scratch probe that imports run_isort from src/ and runs it over this repo's src/ and tests/, or state explicitly that the MCP server must be restarted before the check counts.", 'In pr_info/steps/step_1.md around line 234, fix the non-matching fixture line: it uses warn(f"Unable to parse file {file}") without " due to ", so it cannot match _UNPARSABLE_RE by construction. Model the fixture on isort\'s real emission ("Unable to parse file {file} due to {error}") and choose a genuinely non-matching line for the skip test, or restate what the test is meant to prove.'], escalate_reason=None)
**Changes**:
applied

## Round 3 — 2026-08-31
**Findings**:
I'll gather context now.No critical or high findings. Report:

`pr_info/steps/step_1.md:176` — medium — `_unparsable_block(step, files)` hardcodes check-mode wording ("they were NOT checked", "A clean result here does NOT mean CI will pass") while the plan emits the block in both modes; `_format_results` already receives `check_only` (`formatter_tools.py:98`), so passing it through and branching the wording is one line. Raised in rounds 1 and 2, never tasked, still open.

`pr_info/steps/step_1.md:334` — medium — the probe diagnostic "`parsed: 0` while `warnings` is non-zero means the message is wrapped" does not match the appendix's own wrap point: there `" due to "` sits on the first line, so `_UNPARSABLE_RE` matches and returns a correct path. The failure mode a wrap actually produces is a *truncated* path with `parsed` non-zero, which the stated criterion (`parsed == warnings`, no `{`) will not catch.

`pr_info/steps/step_1.md:164` — low — "a wrapped message yields nothing rather than a glued-together path" is false for the wrapping shown in the issue's appendix, where the regex matches on the first line alone.

`pr_info/steps/step_1.md:223` — low — the fixture is specified as "**verbatim**, prefix included", but the CONSTRAINTS section at line 283 forbids the trigger character that the real message contains; the sample at line 232 silently drops it. The two instructions conflict on their face.
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
dismiss
