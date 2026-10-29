# Step 4: toolkit maps `verdict.status` to `ActionResult`

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_4.md`. Write the mapping tests in `tests/test_toolkit_test.py` first, with `mcp_tools_py.toolkit.check_code_with_pytest` patched. Then update `_run_test` in `src/mcp_tools_py/toolkit.py`. Run pylint, mypy, pytest (`-n auto`), lint-imports and tach, and make sure all of them pass. Run `run_format_code`, then make one commit.

## WHERE

- `src/mcp_tools_py/toolkit.py`: `_run_test`
- `tests/test_toolkit_test.py`

## HOW

```python
from mcp_tools_py.code_checker_pytest.verdict import (
    RunStatus, cap_problems, format_error_text, format_suspicious_text,
)
```

`cap_problems` is the same cap that `format_error_text` uses for its problem lines.

The toolkit must not import `checker_tools`.

## ALGORITHM

This logic goes inside the existing `try`, right after `check_code_with_pytest(...)`:

```text
verdict, report = result["verdict"], result.get("test_results")
if verdict.status not in (PASSED, FAILED, SUSPICIOUS):          # ERROR and unknown statuses
    if any("No Tests Found" in p for p in verdict.problems): return ActionResult("skipped", summary="\n".join(verdict.problems))
    return ActionResult("error", summary=format_error_text(report, verdict))
findings = [...unchanged...]
if verdict.status is FAILED and not findings:
    return ActionResult("error", summary=f"{summary_text}\n\n{cap_problems(verdict.problems)}")
ok_summary = format_suspicious_text(report.summary.collected) if verdict.status is SUSPICIOUS else summary_text
action_result = _result_from_findings(error=None, findings=findings, ok_summary=ok_summary, findings_summary=summary_text)
# coverage digest unchanged: tests_failed=bool(findings)
```

Update the `_run_test` docstring's Returns block so it lists the new mapping.

## DATA

`_run_test` returns an `ActionResult` with `status` set to one of `ok`, `findings`, `error` or `skipped`.

## Tests (written first)

Patch `mcp_tools_py.toolkit.check_code_with_pytest` and use `make_pytest_results` together with small hand-built `PytestReport` objects.

1. `ERROR` with a report (exit 1, passed 3) gives `status == "error"`, and the summary contains "reported an error".
2. `ERROR` from the exception path, with problems `["No Tests Found: …"]` and no report, gives `status == "skipped"`, and the summary is the problem text without "reported an error".
3. `SUSPICIOUS` gives `status == "ok"`, and the summary contains "Not verified".
4. `FAILED` with a failing test gives `status == "findings"`, as today.
5. `FAILED` with no failing tests but a problem, for example a failed collector, gives `status == "error"`, and the summary contains both `summary_text` and the problem.
6. `PASSED` gives `status == "ok"`.

The existing real-run tests in this file must keep passing.
