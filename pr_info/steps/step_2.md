# Step 2: Failure reply

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`. Implement step 2 only, tests first. Run format, pylint, pytest (`-n auto`, `-m "not integration"`) and mypy until they pass. Produce exactly one commit: `feat(pytest): lead failure replies with counts and unrun tests (#49)`.

## Precondition

`create_prompt_for_failed_tests` is still called in the `RunStatus.FAILED` branch of `_format_pytest_result_with_details` in `src/mcp_tools_py/checker_tools/__init__.py`. If not, write one line to `pr_info/.blocked.txt` and stop.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/reporting.py`
- `src/mcp_tools_py/checker_tools/__init__.py`
- `README.md`
- `tests/test_code_checker_pytest/test_reporting.py`
- `tests/test_checker_tools_formatting.py`

## WHAT

In `reporting.py`:

```python
def selected_count(summary: Summary) -> int:
    """Return the tests left after deselection; an absent count means zero."""

def did_not_run_line(report: PytestReport) -> str:
    """Render how many selected tests did not run, or "" when all ran."""
```

Add `Summary` to the existing `models` import. Use `selected_count` in `get_test_summary` in place of its inline subtraction.

## ALGORITHM

```python
def did_not_run_line(report):
    selected = selected_count(report.summary)
    missing = selected - report.summary.total
    if missing <= 0:
        return ""
    return f"{missing} of {selected} selected tests did not run"
```

Formatter, in the `FAILED` branch after the failed-tests prompt is built:

```python
counts = "\n".join(filter(None, [test_results.get("summary_text"), did_not_run_line(report)]))
text = f"Pytest found issues that need attention:\n\n{failed_tests_prompt}"
return "\n\n".join(filter(None, [counts, format_collection_problems(verdict), text]))
```

## HOW

- Import `did_not_run_line` in `checker_tools/__init__.py` from `code_checker_pytest.reporting`.
- The branch for `report is None` or no details stays unchanged, and it already leads with `summary_text`.
- `toolkit.py` doesn't change. It already leads with `summary_text` and doesn't get the did-not-run line.
- Don't use the exit code or the `stopping after N failures` line. Both differ under xdist and `--sw`.
- `README.md:78`: after "Test failures show the failure details", state that the reply starts with the counts, plus `N of M selected tests did not run` when a stop option such as `-x` or `--maxfail` left tests unrun.

## DATA

The reply is now:

```text
Collected 4 tests in 0.10 seconds | ✅ Passed: 1 | ❌ Failed: 1
2 of 4 selected tests did not run

Collection problems:          (only with the xdist hint)
...

Pytest found issues that need attention:
...
```

## Tests (write first)

`tests/test_code_checker_pytest/test_reporting.py`

- Parametrize `did_not_run_line` with synthetic `Summary` values, so the tests don't depend on xdist timing:

  | collected | total | deselected | expected |
  |---|---|---|---|
  | 4 | 2 | absent | `2 of 4 selected tests did not run` |
  | 4 | 1 | 2 | `1 of 2 selected tests did not run` |
  | 2 | 2 | absent (xdist with `-k`) | `""` |
  | 4 | 2 | 2 | `""` |
  | 2 | 3 | absent | `""` |

`tests/test_checker_tools_formatting.py`

- `:286` (`test_format_pytest_result_failed_with_collection_errors`): pass a `summary_text`. The result starts with it, and `Collection problems:` comes before `Pytest found issues`.
- `:308` (`test_format_pytest_result_plain_failed_has_no_collection_block`): pass a `summary_text`. The result starts with it, followed by a blank line and `Pytest found issues that need attention:`.
- Add: a report with `Summary(collected=4, total=2, passed=1, failed=1)` gives the did-not-run line directly after `summary_text`.
- Add: a report with `collected == total` has no `did not run` text.

Tests passing `test_results=MagicMock()` into the `FAILED` path (for example `:132`, plus any in `tests/test_server_params.py` and `tests/test_final_validation.py`) can now fail with a `TypeError`, because `did_not_run_line` does arithmetic on the mock. Give those mocks a real `Summary`, such as `report.summary = Summary(collected=7, total=7)`. Don't add defensive code to production for them.
