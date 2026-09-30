# Summary — #239: `-s` never shows print output from passing tests

## Problem

`-s` in `extra_args` turns off pytest's capture. pytest-json-report then records `None` for stdout, and a passing run's reply is only the summary line. So the output of `print()` calls in passing tests is never shown. With `-n auto` from `addopts`, `-s` also destroys failing-test output, because the existing strip only looks for `-n` in `extra_args`.

## Approach

Treat `-s` as a request to see output, not as a pytest flag.

- `sanitize_extra_args` always removes `-s` and its other spellings and sets `SanitizedArgs.show_output`.
- On a passing run with `show_output` set, the reply adds the stdout and stderr that json-report captured for the setup, call and teardown stages of each passing test that printed.
- How tests run never changes. json-report captures output both serially and under xdist.

## Architectural / design changes

- **Argument sanitizing** (`code_checker_pytest/utils.py`)
  - The xdist-aware `-s` strip and its "worker crashes" note are removed.
  - The existing loop gains two branches:
    - Single-dash tokens made only of `x v s q l` letters are split into separate flags. Each `v` group sets `verbosity` (the last group wins), `s` sets `show_output`, and `x`, `q` and `l` are passed on as their own flags. This subsumes the old exact `-v`/`-vv`/`-vvv` match.
    - `--capture=no` and `--capture no` set `show_output` and are removed. Other `--capture` values pass through.
  - A fixed note is added when `show_output` is set. `pytest_tool` already puts notes in front of the reply.
- **Data model** (`code_checker_pytest/models.py`): `SanitizedArgs` gains `show_output: bool = False`.
- **Reporting** (`code_checker_pytest/reporting.py`): the new `create_prompt_for_passing_output(report, max_output_lines)` lists tests outside `FAILED_OUTCOMES` whose setup, call or teardown stage has non-empty stdout or stderr. It never shows longrepr. It uses `OutputBuilder`, so the output is cut at `MAX_OUTPUT_LINES`. If no test printed, it says so.
- **Wiring** (`checker_tools/__init__.py`, `checker_tools/pytest_tool.py`): `_format_pytest_result_with_details` gains `show_output: bool = False`. Only its success branch uses it, adding the passing-output block. The failing branch is unchanged, so a mixed run shows only failing-test output, as today.

## Known gaps (documented, not fixed)

- An `-s` in the target project's `addopts` or in `PYTEST_ADDOPTS` still disables capture.
- Prints at import or collection time are not stored per test, so they are not shown.

## Files

Modified:

- `src/mcp_tools_py/code_checker_pytest/models.py`: `SanitizedArgs.show_output`
- `src/mcp_tools_py/code_checker_pytest/utils.py`: `sanitize_extra_args`
- `src/mcp_tools_py/code_checker_pytest/reporting.py`: `create_prompt_for_passing_output`
- `src/mcp_tools_py/checker_tools/__init__.py`: `_format_pytest_result_with_details(..., show_output)`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`: passes the flag; docstring for `-s`
- `src/mcp_tools_py/code_checker_pytest/runners.py`: docstring examples, replacing `-xvs`
- `tests/test_code_checker_pytest/test_extra_args.py`
- `tests/test_code_checker_pytest/test_reporting.py`
- `tests/test_checker_tools.py`
- `tests/test_server_params.py`

Created:

- `tests/test_code_checker_pytest/test_integration_show_output.py`

## Steps

1. [step_1.md](./step_1.md): `sanitize_extra_args` removes `-s` and its other spellings, splits combined short flags and sets `show_output`.
2. [step_2.md](./step_2.md): `create_prompt_for_passing_output` and its wiring into the pytest reply.

## Merge note

PR #240 (open) also changes `SanitizedArgs` and `pytest_tool.py`. Rebase after it merges. If both features are present, the passing-output block goes before the coverage digest.
