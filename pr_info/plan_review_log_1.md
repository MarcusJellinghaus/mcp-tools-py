# review-plan review log 1

## Round 1 — 2026-09-30
**Findings**:
Checking whether the formatter test fixtures carry `message`/`location`, which Step 1 would make required.`pr_info/steps/step_4.md:34` — low — `cwe_id = issue_cwe.get("id") or 0` drops the current `isinstance(issue_cwe, dict)` guard in `code_checker_bandit/parsers.py`, so an `issue_cwe` that is not a dict (for example a string) would raise `AttributeError` instead of omitting the CWE line. Keep the guard.

`pr_info/steps/step_2.md:42` — low — Only the `run_ruff_check` docstring in `ruff_check_tool.py` is updated. The `run_ruff_fix` tool docstring should also say that `--statistics` is rejected, because callers of that tool will hit the new error too.

`pr_info/steps/summary.md:27` — low — The issue lists ruff `code` as a required field that must be present and non-null. The plan instead turns a null `code` into `"invalid-syntax"`, which is needed to keep the existing `code: None` case in `tests/test_ruff_imports_runner.py` (`test_syntax_error_still_runs_fix`) passing. The plan should state this as an intentional deviation from the issue so the implementer does not "fix" it back.
**Decisions**:
Verdict(decision='tasks', tasks=['In pr_info/steps/step_4.md:34, keep the existing isinstance(issue_cwe, dict) guard from code_checker_bandit/parsers.py when reading the CWE id, so a non-dict issue_cwe omits the CWE line instead of raising AttributeError.', 'In pr_info/steps/step_2.md, also update the run_ruff_fix tool docstring in ruff_check_tool.py to say that --statistics is rejected, matching the run_ruff_check docstring change.', 'In pr_info/steps/summary.md:27, state that mapping a null ruff `code` to "invalid-syntax" is an intentional deviation from the issue\'s \'code required and non-null\' rule. Note that it keeps tests/test_ruff_imports_runner.py::test_syntax_error_still_runs_fix passing.'], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-09-30
**Findings**:
Checking whether the formatter's ruff test fixtures carry the fields Step 1 makes required.Checking existing ruff runner tests that assert exact command lists.`pr_info/steps/step_1.md:36` — high — The algorithm checks `code`/`message`/`filename` before location. The `--statistics` entries have `code` but no `message` or `filename`, so they fail that first check and get "entries without code, message or filename". The test at `pr_info/steps/step_1.md:61-63` asserts "without locations", as does the issue's example message. Fix: check location first, or make the test assert the message the algorithm produces.

`pr_info/steps/step_1.md:44` — low — `parse_ruff_json_output` is shared with `formatter/ruff_runner.py`, which passes no `extra_args`. On a `ruff_format`/`ruff_imports` parse failure, the fixed suffix "an argument in extra_args probably changed the output shape" therefore points at something that doesn't exist.

`pr_info/steps/step_4.md:30` — low — Put the new `results` list check before the existing debug log `len(data.get("results", []))`. As written, the plan only says "after the `isinstance(data, dict)` check". With a non-sized `results` such as an int, `len()` would raise before the check could return its error.
**Decisions**:
Verdict(decision='tasks', tasks=["In pr_info/steps/step_1.md:36, reorder the validation so the missing-location check runs before the code/message/filename check. That way `--statistics` entries produce the 'without locations' error that the test at step_1.md:61-63 and the issue's example message expect.", "In pr_info/steps/step_1.md:44, make the 'an argument in extra_args probably changed the output shape' suffix conditional, either as a caller-supplied hint or only when extra_args were passed. Callers in formatter/ruff_runner.py pass no extra_args, so they must not get this hint.", 'In pr_info/steps/step_4.md:30, place the new `results` list-type check before the existing debug log that calls `len(data.get("results", []))`. This stops a non-sized `results` value from raising before the check can return its error.'], escalate_reason=None)
**Changes**:
applied

## Round 3 — 2026-09-30
**Findings**:
Checking the pylint and bandit parsers against steps 3 and 4.NO FINDINGS
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
dismiss
