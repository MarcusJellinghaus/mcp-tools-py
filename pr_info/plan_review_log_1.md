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
