# Step 3: Treat only exit code 5 as No Tests Found

**Commit:** `fix(pytest): report a run where every collector fails as an error`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_3.md`. Implement step 3 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit. Also run `tests/test_code_checker_pytest/test_integration_collection_errors.py`, which the default marker selection skips.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/runners.py`
- `tests/test_code_checker_pytest/test_integration_collection_errors.py` (new)
- `tests/test_toolkit_test.py`

## WHAT

No new functions. Changes in `run_tests`:

- `:332`: `if process.returncode == 5:`.
- `:401-405`: remove the `"collected 0 items"` branch, and de-indent the `else` body, so a missing report file always takes the "no report file" path.

The `elif process.returncode == 5 and report_exists:` branch at `:380` is now unreachable, because `:332` raises first on exit 5. It was already unreachable before this change; leave it.

## HOW

Pytest prints `collected 0 items / N errors` when every collector fails serially. That exit 2 run now reaches `parse_pytest_report`, and `classify_run` returns ERROR with the grouped problems.

## DATA

`check_code_with_pytest` returns `test_results` and an ERROR verdict with exit code 2 for that run. `format_error_text` shows the grouped collectors with no exit-code line.

## TESTS

`test_integration_collection_errors.py`, marked `integration`, with real projects in `tmp_path`:

- Serial run where every test module fails to import: ERROR, report present, `collectors failed` in the text, `No Tests Found` absent.
- Two `conftest.py` files in sibling directories failing for different causes, with no failing test, under `-n 2` (skip with `pytest.importorskip("xdist")`): both causes appear in `format_error_text`, and it has no `tests failed` text.
- Two test modules with syntax errors: two distinct errors.
- An empty test directory still gives `No Tests Found`.

`test_toolkit_test.py`: add a test where every test module fails to import, using `PythonToolkit().run` at depth `standard`. It returns `status == "error"`, not `skipped`. Mark it `integration`.

The mocked tests in `test_code_checker/test_runners.py` that set `stdout = "collected 0 items"` all use `return_code = 5`, so they stay as they are.
