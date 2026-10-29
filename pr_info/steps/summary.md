# Summary: explicit pytest run verdict (issue #257)

## Problem

When pytest-xdist workers collect different test sets, xdist aborts and no test runs. `run_pytest_check` still prints `Pytest check completed. Collected N tests …`. The formatter treats any outcome it does not recognise as success.

## Design changes

### One verdict, computed once

A new pure module, `code_checker_pytest/verdict.py`, owns the decision about what a run means. Everything downstream reads its result and nothing re-derives it.

- `RunStatus` is a `str` Enum: `PASSED`, `FAILED`, `ERROR`, `SUSPICIOUS`.
- `RunVerdict` is a frozen dataclass with fields `status: RunStatus`, `problems: list[str]` and `exit_code: int`.
- `classify_run(report)` applies these rules; the first match wins:
  1. `summary.failed` or `summary.error` above 0 gives `FAILED`.
  2. A non-zero `error_context.exit_code` gives `ERROR`. A missing `ErrorContext` counts as exit code 0.
  3. Exit code 0, `collected > 0`, and passed, failed, error, skipped, xfailed and xpassed all zero or None gives `SUSPICIOUS`.
  4. Anything else is `PASSED`.
- The exception path does not call `classify_run`. The `except` block of `check_code_with_pytest` builds `RunVerdict(ERROR, [str(e)], 0)` directly.

### Result dict of `check_code_with_pytest`

- Removed: `success`, `error_info` and `error`.
- Added: `verdict`.
- Unchanged: `summary`, `summary_text`, `failed_tests_prompt` and `test_results`.
- `success` is not kept as a derived alias, because that would recreate two sources of truth.

### Fail-closed formatting

The formatter and `toolkit.py` branch on `verdict.status`.

- Only `PASSED` prints "completed".
- `ERROR` and any unknown status share one `else` branch, which renders the shared ERROR text.

### Shared text helpers in `verdict.py`

The toolkit must not depend on the `checker_tools` formatter, so the shared text lives in `verdict.py`.

- `format_error_text(report | None, verdict)` builds the ERROR text, used by both the formatter and the toolkit.
- `format_suspicious_text(collected)` builds the SUSPICIOUS text, used by both the formatter and the toolkit.
- `format_collection_problems(report, verdict)` builds the "Collection problems" block for the FAILED path in the formatter.
- `cap_problems(problems)` applies the shared line cap. The toolkit also uses it for the problems of a FAILED run with no findings.

### Problem messages

Problems are merged from three sources, in this order:

1. The failed collectors' `longrepr`.
2. `ErrorContext.collection_errors`, joined into one entry.
3. Only for `ERROR`, and only when both are empty: the last 50 lines of `ErrorContext.error_message`. `ErrorContext` holds the full output on every non-zero exit, so a normal `FAILED` run must not pick it up.

The FAILED-path "Collection problems" block shows only `collection_errors` and the xdist hint.

De-duplication uses one key: `"Different tests were collected"` when the text contains it, and otherwise the text's first line. This also covers exact duplicates.

### Rendering problems

- The size cap reuses `reporting.OutputBuilder`, capped at `MAX_OUTPUT_LINES`, which already adds the truncation marker. No new truncation code is needed.
- The xdist hint is appended after capping, so it survives truncation.
- The exit-code line comes from `get_pytest_exit_code_info(verdict.exit_code)`. It is omitted when the code is 0, and also when the code is 2 and the report has collection problems (failed collectors or `collection_errors`), because "interrupted by the user" is misleading there.

### Layering

`verdict.py` imports only `code_checker_pytest.models`, `.reporting` and `.utils`. It never imports `checker_tools` or `toolkit`. The existing `.importlinter` and `tach.toml` layouts already allow this, so neither file changes.

## Output per status (`run_pytest_check`)

| Status | Text |
|---|---|
| `PASSED` | `Pytest check completed. {summary_text}`, as today. `show_output` appends captured output only here. |
| `FAILED` | The "Collection problems" block, if non-empty, followed by `Pytest found issues that need attention:\n\n{prompt}`. When the report is missing or `show_details=False`: `Pytest found failures. {summary_text}`. |
| `SUSPICIOUS` | `Collected N tests but none reported an outcome. Not verified.` |
| `ERROR` / unknown | The `Pytest run reported an error.` headline, then the counts, or `Pytest run did not complete.` when there are no outcomes, then the exit-code line, then `Problems:` with the capped problems and the xdist hint. |

## Toolkit mapping (`PythonToolkit` test action)

| Status | `ActionResult` |
|---|---|
| `PASSED` | `ok` |
| `SUSPICIOUS` | `ok`, with the summary set to `format_suspicious_text(...)` |
| `FAILED` | `findings`, as today. When there are no findings: `error`, with `summary_text` plus the capped problems. |
| `ERROR` / unknown | `skipped` with the problem text if any problem contains `"No Tests Found"`, otherwise `error` with `format_error_text(...)` |

## Files

### Created

- `src/mcp_tools_py/code_checker_pytest/verdict.py`
- `tests/test_code_checker_pytest/test_verdict.py`
- `tests/_pytest_results.py`: the test helper `make_pytest_results(...)`
- `tests/test_code_checker_pytest/test_integration_xdist_collection.py`

### Modified

- `src/mcp_tools_py/code_checker_pytest/__init__.py`: exports
- `src/mcp_tools_py/code_checker_pytest/runners.py`: `check_code_with_pytest`
- `src/mcp_tools_py/checker_tools/__init__.py`: `_format_pytest_result_with_details`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`: `tests_failed` and logging
- `src/mcp_tools_py/toolkit.py`: `_run_test`
- `README.md`: the xdist note and the statuses note
- Test files migrated from `success` to `verdict`:
  - `tests/test_checker_tools_formatting.py`
  - `tests/test_final_validation.py`
  - `tests/test_server_params.py`
  - `tests/test_code_checker/test_runners.py`
  - `tests/test_code_checker_pytest/test_reporting.py`
  - `tests/test_code_checker_pytest/test_runners.py`
  - `tests/test_tool_availability/test_handler_short_circuit.py`
- `tests/test_toolkit_test.py`: mapping tests

### Unchanged

`ErrorContext`, `get_test_summary`, `run_tests` and the `run_pytest_check` parameters.

## Steps

The issue planned four commit-sized steps. Its step 3 bundles three independent consumers, so it is split here into steps 3–5, one commit each.

1. [step_1.md](step_1.md): `verdict.py` and its unit tests.
2. [step_2.md](step_2.md): `check_code_with_pytest` returns `verdict`. Test dicts are migrated, and the three consumers get minimal reads.
3. [step_3.md](step_3.md): formatter branches on the status.
4. [step_4.md](step_4.md): toolkit mapping.
5. [step_5.md](step_5.md): `pytest_tool` sets `tests_failed` and logging from the verdict.
6. [step_6.md](step_6.md): xdist integration test and README.
