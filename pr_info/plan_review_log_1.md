# review-plan review log 1

## Round 1 — 2026-10-29
**Findings**:
Verifying the plan against the actual `runners.py`, formatter and toolkit code.pr_info/steps/step_1.md:78 — high — When there are no collector or `collection_errors` problems, `_merge_problems` falls back to the last 50 lines of `error_message`. But `runners.py:336-340` builds an `ErrorContext` holding the full combined output on every non-zero exit, so an ordinary failing run (exit 1) also gets that tail as a problem. `format_collection_problems` (step_1.md:92-96) only filters out collector `longrepr`, so every normal FAILED run would start with a "Collection problems:" block of up to 50 lines of raw pytest output. The issue limits that block to `collection_errors` and the xdist hint. Restrict the block to those two, or apply the tail fallback only when the status is ERROR.
pr_info/steps/step_3.md:51 — medium — There is no formatter test for a plain FAILED run (exit 1, an `error_context` with only `error_message`, no failed collectors or `collection_errors`) asserting that the output has no "Collection problems:" block. That is exactly the regression in the finding above, and the plan's tests would not catch it.
pr_info/steps/step_3.md:5 — low — The prompt says only `tests/test_final_validation.py` asserts the old "Error running pytest" wording. `tests/test_checker_tools_formatting.py:226` asserts it too and also needs updating in this step.
**Decisions**:
Verdict(decision='tasks', tasks=["In pr_info/steps/step_1.md, restrict the 'Collection problems:' block to collection_errors entries and the xdist hint. Do not fall back to the last 50 lines of error_message for ordinary failing runs. Apply that tail fallback only when the status is ERROR (no tests ran), so a normal FAILED run (exit 1) gets no 'Collection problems:' block.", "In pr_info/steps/step_3.md, add a formatter test for a plain FAILED run (exit 1, error_context with only error_message, no failed collectors or collection_errors) asserting the output has no 'Collection problems:' block.", "In pr_info/steps/step_3.md, also list tests/test_checker_tools_formatting.py:226 as a test that asserts the old 'Error running pytest' wording and needs updating in this step."], escalate_reason=None)
**Changes**:
applied

## Round 2 — 2026-10-29
**Findings**:
Now verify the plan against the actual code.Checking two remaining details (the coverage digest wording and the test that checks that `success` was removed), then I'll write the report.pr_info/steps/step_4.md:29 — low — For a "No Tests Found" result, the `skipped` summary uses `format_error_text`, so a skip reads "Pytest run reported an error. / Pytest run did not complete." Today the summary is the raw message. Using `"\n".join(verdict.problems)` for the skipped summary would avoid calling a skip an error.
pr_info/steps/step_4.md:33 — low — The summary for `FAILED` with no findings joins `verdict.problems` without a size cap. Collector `longrepr` text can be long, so it should go through the same `_cap_lines` cap that the ERROR text uses.
pr_info/steps/step_1.md:101 — low — `_cap_lines` relies on `OutputBuilder.add` to add the truncation marker. Per `reporting.py:64-73`, `add` adds no marker when the earlier problems fill exactly `MAX_OUTPUT_LINES` (`remaining_lines == 0`). The cap test at step_1.md:134 should use problems that overflow partway through an item, or `_cap_lines` should append the marker itself when `add` returns False.
**Decisions**:
Verdict(decision='tasks', tasks=['In pr_info/steps/step_4.md:29, build the \'No Tests Found\' skipped summary from "\\n".join(verdict.problems) instead of format_error_text, so a skip is not described as an error.', 'In pr_info/steps/step_4.md:33, cap the joined verdict.problems summary for FAILED-with-no-findings with _cap_lines, the same cap used for the ERROR text.'], escalate_reason=None)
**Changes**:
applied
