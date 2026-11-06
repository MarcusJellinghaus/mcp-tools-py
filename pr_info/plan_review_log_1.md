# review-plan review log 1

## Round 1 — 2026-11-06
**Findings**:
Checking one remaining risk before I emit the report: `parsers.py` never mentions `deselected`, and both the collect-only IDs and the deselected count depend on it.`pr_info/steps/step_3.md:100` — medium — No planned test covers the `collect_only=sanitized.collect_only` wiring in `pytest_tool.py`: the tests call the sanitizer and the formatter separately, and the integration helper stops at `run_tests`. If the wiring is omitted, all tests still pass while `run_pytest_check(["--collect-only", ...])` keeps replying `Not verified`, the symptom in issue item 2. Add a tool-level test that goes through `run_pytest_check` with a mocked `check_code_with_pytest` returning a SUSPICIOUS result, asserting the reply has the header and IDs and no `Not verified`.
`pr_info/steps/step_3.md:101` — medium — The corrected suspicious count has no test on either caller's wiring (`runners.py` `summary_dict`, `toolkit.py:215`, step_3.md:102): the formatter test at step_3.md:138 hand-builds `{"collected": 4, "deselected": 3}`, and `format_suspicious_text(4, 3)` is tested directly. If either change is omitted, the default `deselected=None` keeps the raw count and no test fails, though the issue requires the fix for both callers. Assert `summary["deselected"]` from a real `check_code_with_pytest` run, and add a case beside `test_suspicious_is_ok_not_verified` in `tests/test_toolkit_test.py:194` using a report with deselected tests.
**Decisions**:
Verdict(decision='tasks', tasks=['In pr_info/steps/step_3.md, add a planned tool-level test for the `collect_only=sanitized.collect_only` wiring in `pytest_tool.py`: call `run_pytest_check` with `--collect-only` and a mocked `check_code_with_pytest` returning a SUSPICIOUS result, then assert the reply contains the header and test IDs and does not contain `Not verified`.', 'In pr_info/steps/step_3.md, add planned tests for the corrected suspicious count on both callers: assert `summary["deselected"]` from a real `check_code_with_pytest` run to cover `runners.py` `summary_dict`, and add a case beside `test_suspicious_is_ok_not_verified` in `tests/test_toolkit_test.py` using a report with deselected tests to cover `toolkit.py`.'], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-11-06
**Findings**:
Plan review is nearly done: I've checked the plan against the source and tests, and I'm confirming the last test references.`pr_info/steps/summary.md:50` — low — The Files table is out of step with `step_3.md:22-28`: `test_reporting.py` is listed for step 2 only, though step 3 also changes it, and `tests/test_server_params.py` and `tests/test_toolkit_test.py` have no rows. Add step 3 to the `test_reporting.py` row and add rows for the other two files.
**Decisions**:
Verdict(decision='dismiss', tasks=[], escalate_reason=None)
**Changes**:
dismiss
