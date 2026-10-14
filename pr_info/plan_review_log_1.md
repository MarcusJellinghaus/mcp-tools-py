# review-plan review log 1

## Round 1 — 2026-10-14
**Findings**:
I'll gather the knowledge base principles, the issue chain, and the plan files.Now let me read the epic #1192 in mcp_coder and the toolkit base class issue #41 in mcp-coder-utils, plus the actual plan step files.I have enough to finalize the structured report.```
pr_info/steps/summary.md:35 — high — Summary claims a "tool name → MCP tool name" dispatch table drives both run() and describe()'s llm_permissions "so the two can't drift apart," but no such table exists in any step: step_1.md hardcodes llm_permissions as a static literal dict (step_1.md:54-73) before _CHECK_RUNNERS/_CHECK_DEPTHS exist, and step_3.md/step_4.md's _CHECK_RUNNERS maps tool name → run function, not tool name → MCP tool name. The two mappings (literal llm_permissions vs. _CHECK_RUNNERS/_CHECK_DEPTHS) are maintained independently, so they can in fact drift — contradicting the stated design goal.

pr_info/steps/step_4.md:62 — medium — Algorithm heading says degraded tools get "single finding per action+depth," but the concrete key format on step_4.md:69 (and the lint-imports/tach equivalents) is `f"{tool}|{depth}"` (tool name, not action name). Using the literal action name ("check") for all three degraded tools would make their findings collide under one key within the same check@full result, so the documented key scheme (summary.md and the heading here) is inconsistent with the one actually needed and implemented.

#245 (Done when) / pr_info/steps/step_3.md — high — Issue #245's Done-when explicitly requires tests covering "the status-validation edge cases inherited from ActionResult (unknown status, findings with none, ok/skipped with findings)." No step (1–5) plans a test exercising these ActionResult construction/validation paths; the planned tests only cover the toolkit's own ok/findings/error/skipped branching, never a case that would trigger ActionResult's own ValueError rules.

pr_info/steps/summary.md:1 — medium — All five steps accumulate tests into a single tests/test_toolkit.py with no planned split, across skeleton+describe, format, check(quick/standard), check(full, 5 tools), and verify. Given the number of scenarios (10+ per later step), this risks exceeding the project's file-size check before step 5 completes, and no step addresses splitting the test file.
```
**Decisions**:
Verdict(decision='tasks', tasks=["Fix pr_info/steps/summary.md:35 — remove or correct the claim that a single tool-name-to-MCP-tool-name dispatch table drives both run() and describe()'s llm_permissions; either introduce that single table and derive both llm_permissions and _CHECK_RUNNERS/_CHECK_DEPTHS from it, or rewrite the summary to describe the two mappings as separately maintained and note the drift risk explicitly.", 'Fix pr_info/steps/step_4.md:62 — align the \'single finding per action+depth\' wording with the actual key format f"{tool}|{depth}" used at step_4.md:69 (and the lint-imports/tach equivalents); state the key is keyed by tool name, not action name, so findings from different degraded tools don\'t collide.', "Add a planned test step (in step_3.md or wherever check()'s ActionResult construction is tested) that exercises ActionResult's own status-validation edge cases — unknown status, findings with none, ok/skipped with findings — as required by issue #245's Done-when criteria; current plan only tests the toolkit's ok/findings/error/skipped branching, not ActionResult's own validation rules.", "Address pr_info/steps/summary.md:1 — add a plan note (in step 5 or summary.md) for splitting tests/test_toolkit.py once it grows past the project's file-size limit, given 10+ scenarios accumulate across steps 1-5 into one file."], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-10-14
**Findings**:
I'll start by reading the knowledge base principles, the issue, and the plan files.Good — `"lint-imports"` key matches exactly what the plan uses. No naming mismatch there.

Now let me check the formatter runner and resolve_target_directories signatures referenced in steps 2–4 to confirm they exist as described.Let me get precise line numbers for the gap found in steps 3 and 4.Confirmed: `dirs` at line 58 ("All five resolve target directories via `resolve_target_directories`") is never checked for the error-string return, and `_run_ruff` (lines 49-54, 88-90) never checks `execute_command`'s `timed_out`/`execution_error` before parsing — unlike the `tach` case three lines above it in the same algorithm block.

I have what I need for the round-2 report.

**Findings:**

```
pr_info/steps/step_3.md:38 — high — resolve_target_directories (used for both mypy and pylint) returns list[str] | str, with str meaning a config error — every existing checker_tools/* registrar (e.g. mypy_tool.py) checks `isinstance(resolved, str)` and returns that error immediately. Step 3's HOW/DATA for _run_mypy/_run_pylint never mentions this branch, so as specified the toolkit would pass an error string where a list[str] is expected.
pr_info/steps/step_4.md:58 — high — Same resolve_target_directories gap for _run_vulture, _run_ruff, _run_bandit: "All five resolve target directories via resolve_target_directories" states the call but never specifies handling its str-error-return case, unlike step 2's format algorithm which explicitly calls out "str return -> error".
pr_info/steps/step_4.md:88 — high — _run_ruff's algorithm (lines 49-54, 88-90) parses execute_command's stdout via parse_ruff_json_output but never checks CommandResult.timed_out/execution_error first, unlike _run_tach three lines above (line 83) in the same ALGORITHM block which explicitly checks them. A ruff timeout or subprocess crash would produce empty/garbage stdout, which parse_ruff_json_output treats as "no violations" — silently reporting status "ok" for a tool that never ran, contradicting the issue's explicit "tool unavailable/failed → error, not findings" rule.
```
**Decisions**:
Verdict(decision='tasks', tasks=["Update step_3.md's HOW/DATA for _run_mypy and _run_pylint to explicitly handle resolve_target_directories' str-error return (config error) by returning/propagating that error immediately, matching the pattern used in existing checker_tools/* registrars (e.g. mypy_tool.py) and in step 2's format algorithm.", "Update step_4.md's algorithm text (around line 58) for _run_vulture, _run_ruff, and _run_bandit to explicitly specify handling resolve_target_directories' str-error return, consistent with the str-error handling already specified for other tools.", "Update step_4.md's _run_ruff algorithm (lines 49-54, 88-90) to check CommandResult.timed_out/execution_error before parsing stdout with parse_ruff_json_output, matching the check already specified for _run_tach, so a ruff timeout or crash reports an error status instead of being misread as 'no violations' / status ok."], escalate_reason=None)
**Changes**:
applied
