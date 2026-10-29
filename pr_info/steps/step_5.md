# Step 5: `pytest_tool` sets `tests_failed` and logging from the verdict

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_5.md`. Write the tests in `tests/test_server_params.py` first. Then update `src/mcp_tools_py/checker_tools/pytest_tool.py`. Run pylint, mypy and pytest (`-n auto`), make sure all of them pass, run `run_format_code`, then make one commit.

## WHERE

- `src/mcp_tools_py/checker_tools/pytest_tool.py`: the `run_pytest_check` body, after the formatter call.
- `tests/test_server_params.py`: class `TestPytestCoverage`, plus a new class `TestPytestVerdictLogging`.

## HOW

```python
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
```

## ALGORITHM

```text
verdict = test_results["verdict"]
tests_failed = verdict.status in (RunStatus.FAILED, RunStatus.ERROR)   # passed to format_coverage_digest
if verdict.status in (PASSED, FAILED): logger.info("Pytest execution completed", extra={counts as today, "status": verdict.status.value})
elif verdict.status is SUSPICIOUS:     logger.warning("Pytest run reported no outcomes", extra={"collected": ...})
else:                                  logger.error("Pytest execution failed", extra={"problems": verdict.problems, "exit_code": verdict.exit_code})
```

This replaces the step 2 placeholder reads (`"test_results" not in test_results` and the joined `problems`).

## DATA

The returned text does not change. Only the digest warning flag and the log levels change.

## Tests (written first)

1. Coverage `tests_failed`:
   - `ERROR` with a report (not the exception path) carries "Warning: tests failed".
   - `SUSPICIOUS` does not.
   - The existing `FAILED` and exception-path tests keep passing.
2. Logging, via `caplog` with the `mcp_tools_py.checker_tools.pytest_tool` logger:
   - `PASSED` and `FAILED` log at INFO.
   - `SUSPICIOUS` logs at WARNING.
   - `ERROR` logs at ERROR, and the record carries `problems` and `exit_code`.
