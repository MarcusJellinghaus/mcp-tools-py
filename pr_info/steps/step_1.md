# Step 1 — Collect count excludes deselected tests

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_1.md` only. Use TDD: write the tests first, then the change. Run pylint, pytest (`-n auto`) and mypy through the MCP tools and make them pass. Run `run_format_code`, then make one commit.

## Precondition

`Summary` in `src/mcp_tools_py/code_checker_pytest/models.py` has a `deselected` field, and the parser fills it in. If it doesn't, write one line to `pr_info/.blocked.txt` and stop.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/reporting.py`: `get_test_summary`
- `tests/test_code_checker/test_reporting.py`

## WHAT

`get_test_summary(test_session_result: PytestReport) -> str` keeps its signature. Only the first part of the header changes.

## ALGORITHM

```
deselected = summary.deselected or 0
selected = summary.collected - deselected
header = f"Collected {selected} tests"
if deselected > 0: header += f" ({deselected} deselected)"
header += f" in {duration:.2f} seconds"
```

Leave `get_detailed_test_summary` and its `show_details` dict unchanged. They keep the raw `collected`.

## DATA

- With deselected tests: `Collected 6 tests (4 deselected) in 0.12 seconds | ...`
- Without them: the output is unchanged, as in `Collected 5 tests in 0.12 seconds`.

## Tests

- `test_get_test_summary_with_deselected`: JSON with `"collected": 10, "deselected": 4` and `"passed": 6`. Assert `"Collected 6 tests (4 deselected) in"` is in the summary.
- The existing `test_get_test_summary` and `test_get_test_summary_minimal` already cover the case without `deselected`. Add an assertion that `"deselected"` isn't in the minimal summary.
