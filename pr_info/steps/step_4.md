# Step 4: Replace `tests_failed` with counts and warning lines; handle no-report runs

**Commit:** `feat(coverage): qualify the digest with failure counts`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_4.md`. Implement step 4 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit. Also run `tests/test_pytest_tool_coverage.py`, which the default marker selection skips.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/coverage.py`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `src/mcp_tools_py/toolkit.py`
- `tests/test_code_checker_pytest/test_coverage.py`
- `tests/test_server_params.py`
- `tests/test_pytest_tool_coverage.py`

## WHAT

In `coverage.py`:

```python
class RunOutcome(TypedDict):
    failed_collectors: int
    failed_tests: int
    generic_warning: bool

def run_outcome(report: PytestReport | None, verdict: RunVerdict) -> RunOutcome: ...
def no_report_message(failed_collectors: int) -> str: ...

def format_coverage_digest(
    data, selection, max_modules=10, fail_under=0.0,
    failed_collectors: int = 0, failed_tests: int = 0, generic_warning: bool = False,
) -> str: ...
```

`coverage.py` may import from `verdict.py` and `reporting.py`; neither imports `coverage.py`.

## HOW

`pytest_tool.py`, replacing the current `tests_failed` block:

```python
report = test_results.get("test_results")
outcome = run_outcome(report, verdict)
data = read_coverage_report(temp_dir) if report is not None else None
digest = (
    no_report_message(outcome["failed_collectors"]) if data is None
    else format_coverage_digest(data, selection, max_modules=max_modules,
                                fail_under=fail_under, **outcome)
)
```

Keep `read_coverage_report` and `format_coverage_digest` called from `pytest_tool.py`, because `test_server_params.py` patches them there. `toolkit.py` calls the digest with `**run_outcome(report, verdict)` instead of `tests_failed=bool(findings)`.

## ALGORITHM

```
report None -> all zero, generic_warning False
failed_collectors = failed_collector_count(report)
failed_tests = (summary.failed or 0) + (summary.error or 0)
generic_warning = verdict.status is ERROR and both counts are 0
```

## DATA

Warning lines come first in the digest, each only when it applies:

```
⚠ 47 collectors failed — coverage below reflects a partial run
⚠ 2 tests failed — coverage below comes from a run with failures
⚠ the pytest run reported an error — coverage below may be incomplete
```

Use the singular for a count of 1. The old `Warning: tests failed` line goes. `no_report_message(0)` is exactly `Coverage report was not produced.`; `no_report_message(47)` is `Coverage report was not produced. 47 collectors failed.`

## TESTS

`test_coverage.py` (later steps put their new test classes in their own modules, so the file stays under the 750-line gate):

- Replace the `Warning: tests failed` test at `:423-430` with a parametrized test: collector line, test line, both in that order, generic line, and none. The first warning is the digest's first line.
- A collection-only digest doesn't contain `tests failed`.
- `run_outcome`: `summary.error` alone counts as a failed test; ERROR with zero counts sets `generic_warning`; PASSED and SUSPICIOUS don't; `None` report gives zeros.
- `no_report_message` with 0 and with 47.

`test_server_params.py`:

- `_pytest_results` (`:833`) returns a real `PytestReport` with a matching `Summary`, or the digest tests using it lose their digest.
- `:991`, `:1037`: assert `⚠` isn't in the reply.
- `:1002`: assert `⚠ 1 test failed` is.
- `:1004-1013`: no parsed report, so expect `Coverage report was not produced.` and no digest.
- `:1015-1024`: expect the generic warning.
- `:1026-1037`: pass a report for the SUSPICIOUS run, so the test isn't vacuous.

`test_pytest_tool_coverage.py:90`: assert `⚠` isn't in the reply.
