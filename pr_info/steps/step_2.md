# Step 2 — Show captured output of passing tests

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_2.md`. Step 1 is already done: `SanitizedArgs.show_output` exists. Use TDD: write the tests listed below first, then add `create_prompt_for_passing_output`, pass `show_output` through `_format_pytest_result_with_details`, and update the docstrings. Run pylint, pytest (`-n auto`) and mypy until all pass. Make exactly one commit.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/reporting.py`: new function
- `src/mcp_tools_py/checker_tools/__init__.py`: new parameter and success-branch use
- `src/mcp_tools_py/checker_tools/pytest_tool.py`: pass the flag, docstring
- `src/mcp_tools_py/code_checker_pytest/runners.py`: docstrings at about lines 102 and 488, replacing `'-xvs'` with `'-x'`
- Tests:
  - `tests/test_code_checker_pytest/test_reporting.py`
  - `tests/test_checker_tools.py`
  - `tests/test_server_params.py`
  - new `tests/test_code_checker_pytest/test_integration_show_output.py`

## WHAT

```python
# reporting.py
NO_CAPTURED_OUTPUT_NOTE = "Note: no passing test produced captured output."

@log_function_call
def create_prompt_for_passing_output(
    test_session_result: PytestReport,
    max_output_lines: int = MAX_OUTPUT_LINES,
) -> str: ...

# checker_tools/__init__.py
def _format_pytest_result_with_details(
    self, test_results: dict[str, Any], show_details: bool, show_output: bool = False
) -> str: ...
```

## HOW

- `checker_tools/__init__.py`:
  - Import `create_prompt_for_passing_output` next to `create_prompt_for_failed_tests`.
  - In the success branch, build the existing summary line into `result`.
  - If `show_output and test_results.get("test_results")`, append `"\n\n" + create_prompt_for_passing_output(test_results["test_results"])`.
  - Return `result`. The failing branch is untouched.
- `pytest_tool.py`:
  - Pass the flag in the call: `_format_pytest_result_with_details(test_results, show_details=True, show_output=sanitized.show_output)`.
  - Change the docstring line to `extra_args=["-s"]  # Show captured print output of passing tests`.
- Use only `OutputBuilder` for truncation. No new helper function.

## ALGORITHM

```
output = OutputBuilder(max_output_lines)
for test in (report.tests or []) where test.outcome not in FAILED_OUTCOMES:
    stages = [(name, s) for name, s in (("Setup", test.setup), ("Call", test.call), ("Teardown", test.teardown)) if s]
    blocks = [(f"{name} {kind}", text) for name, s in stages for kind, text in (("stdout", s.stdout), ("stderr", s.stderr)) if text]
    if not blocks: continue
    if not output.add(f"Test ID: {test.nodeid} - outcome {test.outcome}\n"): break
    for label, text in blocks: if not output.add(f"  {label}:\n```\n{text}\n```\n"): break both loops
return output.get_result() if any test was added, else NO_CAPTURED_OUTPUT_NOTE
```

The header is `"Captured output of passing tests:\n"`, added to `output` once, before the first printing test, and not prepended again on return. Guard the header and the early exit with a simple flag.

## DATA

- The function returns a string: either the header plus one block per test that printed, cut at 300 lines, or `NO_CAPTURED_OUTPUT_NOTE`.
- A passing reply with `-s` looks like this: `"<notes>\n\nPytest check completed. <summary>\n\nCaptured output of passing tests:\nTest ID: ...\n  Call stdout:\n```\nHELLO\n```\n"`.
- Without `-s`, the reply is byte-for-byte unchanged.

## Tests (write first)

`test_reporting.py`: build reports with the existing `parse_pytest_report(json.dumps(...))` pattern.

1. Passed, skipped and xfailed tests with stdout or stderr in setup, call and teardown. All six blocks appear, labelled by stage. An xfailed `call.longrepr` does not appear. A failed test's output does not appear.
2. A passing test with no output is left out. If no test printed, the result equals `NO_CAPTURED_OUTPUT_NOTE`.
3. With many printing tests and `max_output_lines=10`, the result contains `[Output truncated`.

`test_checker_tools.py`:

4. Success with `show_output=True` and a `test_results` report that printed: the summary line and the captured output both appear.
5. Success with `show_output=False`: the result equals today's summary line.
6. Failures with `show_output=True`: `create_prompt_for_failed_tests` is used, and there is no "Captured output of passing tests".

`test_server_params.py`:

7. Calling `run_pytest_check(extra_args=["-s", "-n", "auto"])` with `check_code_with_pytest` patched:
   - `-s` is not in `call_args[1]["extra_args"]`
   - `-n auto` is kept
   - the reply contains `SHOW_OUTPUT_NOTE`

`test_integration_show_output.py` (`@pytest.mark.integration`; follow `test_integration_env.py`):

8. `parametrize` over `["-n", "0"]` and `["-n", "2"]`:
   - Write a temp project with:
     - a fixture that prints `SETUP_PROBE` before `yield` and `TEARDOWN_PROBE` after it
     - a passing test that uses the fixture, prints `HELLO_PROBE` and writes `STDERR_PROBE` to `sys.stderr`
   - Call `run_tests(..., extra_args=<n args>)`.
   - Check that `create_prompt_for_passing_output(report)` contains `SETUP_PROBE`, `HELLO_PROBE`, `TEARDOWN_PROBE` and `STDERR_PROBE`.
