# Step 3: Collect-only

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_3.md`. Implement step 3 only, tests first. Run format, pylint, pytest (`-n auto`, `-m "not integration"`, then `tests/test_code_checker_pytest/test_integration_extra_args.py`) and mypy until they pass. Produce exactly one commit: `feat(pytest): report selected tests and IDs for --collect-only (#49)`.

## Precondition

`_positional_args` exists in `src/mcp_tools_py/code_checker_pytest/utils.py` and `selected_count` exists in `src/mcp_tools_py/code_checker_pytest/reporting.py`. If not, write one line to `pr_info/.blocked.txt` and stop.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/models.py`
- `src/mcp_tools_py/code_checker_pytest/utils.py`
- `src/mcp_tools_py/code_checker_pytest/reporting.py`
- `src/mcp_tools_py/code_checker_pytest/verdict.py`
- `src/mcp_tools_py/code_checker_pytest/runners.py`
- `src/mcp_tools_py/checker_tools/__init__.py`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `src/mcp_tools_py/toolkit.py`
- `README.md`
- `tests/test_code_checker_pytest/test_extra_args.py`
- `tests/test_code_checker_pytest/test_reporting.py`
- `tests/test_code_checker_pytest/test_verdict.py`
- `tests/test_checker_tools_formatting.py`
- `tests/test_code_checker_pytest/test_integration_extra_args.py`
- `tests/test_server_params.py`
- `tests/test_toolkit_test.py`

## WHAT

```python
# models.py, SanitizedArgs
collect_only: bool = False

# utils.py
_COLLECT_ONLY_FLAGS = {"--collect-only", "--co", "--collectonly"}
def _scan_args(args: List[str]) -> Tuple[List[str], bool]: ...  # replaces _positional_args

# reporting.py
def collected_test_ids(report: PytestReport) -> List[str]: ...

# verdict.py
def format_collect_only_text(report: PytestReport) -> str: ...
def format_suspicious_text(collected: int, deselected: int | None = None) -> str: ...

# checker_tools/__init__.py
def _format_pytest_result_with_details(
    self, test_results, show_details, show_output=False, collect_only=False
) -> str: ...
```

## ALGORITHM

`_scan_args`: rename `_positional_args` and return `(positionals, collect_only)`. Before the value loop, add `collect_only = collect_only or arg in _COLLECT_ONLY_FLAGS`. A flag after `--` is a positional, so it isn't detected.

```python
def collected_test_ids(report):
    collectors = report.collectors or []
    collector_ids = {collector.nodeid for collector in collectors}
    return [
        item.nodeid
        for collector in collectors
        for item in collector.result
        if item.nodeid not in collector_ids and not item.deselected
    ]

def format_collect_only_text(report):
    selected, deselected = selected_count(report.summary), report.summary.deselected or 0
    header = f"Collected {selected} {plural(selected, 'test')}"
    if deselected:
        header += f" ({deselected} deselected)"
    output = OutputBuilder(MAX_OUTPUT_LINES)
    output.add(f"{header} in {report.duration:.2f} seconds. No tests were run.\n")
    ids = collected_test_ids(report)
    if ids:
        output.add("\n".join(ids) + "\n")  # one add, so the truncation marker appears
    return output.get_result()
```

`format_suspicious_text` subtracts internally, and the text is otherwise unchanged:

```python
f"Collected {collected - (deselected or 0)} tests but none reported an outcome. Not verified."
```

## HOW

- Add the IDs to `OutputBuilder` in **one** `add` call. Adding them line by line loses the marker: when the count reaches the cap exactly, `OutputBuilder.add` has no remaining lines and sets `truncated` without writing `[Output truncated...]`.
- Don't filter on `type == "Function"`. That drops `Coroutine` tests and `DoctestItem`.
- `sanitize_extra_args`: call `_scan_args(cleaned)` before the `if project_dir:` guard, so `collect_only` is set without a project directory. Loop over the positionals inside the guard. Pass `collect_only` to the returned `SanitizedArgs`.
- `verdict.py`: extend the existing `reporting` import with `collected_test_ids`, `plural` and `selected_count`.
- `_format_pytest_result_with_details`, in the `SUSPICIOUS` branch:

  ```python
  if collect_only and report:
      return format_collect_only_text(report)
  return format_suspicious_text(summary.get("collected") or 0, summary.get("deselected"))
  ```

  Import `format_collect_only_text` from `verdict`. Collection errors exit non-zero, so they never reach this branch.
- `pytest_tool.py`: pass `collect_only=sanitized.collect_only` to `_format_pytest_result_with_details`.
- `runners.py`, `check_code_with_pytest`: add `"deselected": test_results.summary.deselected` to `summary_dict`.
- `toolkit.py:215`: `format_suspicious_text(report.summary.collected, report.summary.deselected)`.
- `README.md:78`: add that a `--collect-only` run reads `Collected N tests ... No tests were run.` followed by the test IDs, capped at 300 lines. Keep the `Not verified` sentence for other runs with no outcomes.

## DATA

```text
Collected 1 test (3 deselected) in 0.05 seconds. No tests were run.
tests/test_x.py::test_a
```

Sanitizer notes stay ahead of this text, because `pytest_tool.py` prepends them. `--json-report-omit collectors` gives no IDs, so the reply is the header alone.

## Tests (write first)

`tests/test_code_checker_pytest/test_extra_args.py`

- `collect_only` is True for `--collect-only`, `--co`, `--collectonly`, and for `-k tests --collect-only -q p.py`, also without a `project_dir`.
- `collect_only` is False for `[]`, `None`, `-x`, and `-- --collect-only`.
- Update the `_positional_args` parametrized test from step 1 to call `_scan_args` and compare the first element.

`tests/test_code_checker_pytest/test_reporting.py`

- `collected_test_ids` with synthetic collectors: it drops deselected items and nodeids that are collectors themselves (`test_x.py::TestK`, `test_x.py::TestEmpty`). It keeps `Coroutine` and `DoctestItem` items, and returns `[]` when `collectors` is `None`.

`tests/test_code_checker_pytest/test_verdict.py`

- `format_collect_only_text`:
  - With 4 collected and 3 deselected, the first line is `Collected 1 test (3 deselected) in 1.00 seconds. No tests were run.`, followed by the ID.
  - With nothing deselected, there is no parenthetical and the noun is plural.
  - With 400 IDs, the count stays on the first line and the text contains `[Output truncated at 300 lines`.
  - With no collectors, only the header is returned.
- `format_suspicious_text(4, 3)` contains `Collected 1 tests`. `test_format_suspicious_text` (`:238`) stays as it is.

`tests/test_checker_tools_formatting.py`

- `SUSPICIOUS` with `collect_only=True` and a real report: starts with `Collected` and has no `Not verified`.
- `SUSPICIOUS` with `collect_only=False` and `summary={"collected": 4, "deselected": 3}`: contains `Collected 1 tests` and `Not verified`.
- `FAILED` and `ERROR` with `collect_only=True`: the same text as without it.

`tests/test_code_checker_pytest/test_integration_extra_args.py`

- Add `tests/test_second.py` with one passing test to the fixture from step 1. A real `--collect-only -k test_in` run through the helper: `report.summary.total == 0`, `report.summary.deselected == 1`, and `collected_test_ids(report)` lists only the test in `tests/test_in.py`. This pins the JSON shape `collected_test_ids` relies on.
- The same run with `-n 2`: the same IDs, because xdist doesn't start workers for collect-only.
- `check_code_with_pytest` on the same project with `--collect-only -k test_in`: `summary["deselected"] == 1`. This covers `summary_dict` in `runners.py`.

`tests/test_server_params.py`

- Beside the existing `run_pytest_check` test (`:75-99`), with the same server setup and mocked `check_code_with_pytest`: call `run_pytest_check(extra_args=["--collect-only"])`, with the mock returning `make_pytest_results(RunStatus.SUSPICIOUS, summary={"collected": 4, "deselected": 3}, test_results=report)`. `report` is a real `PytestReport` with those counts and a collector listing the IDs. The reply contains `Collected 1 test (3 deselected)` and the selected test ID, and doesn't contain `Not verified`. This covers `collect_only=sanitized.collect_only` in `pytest_tool.py`.

`tests/test_toolkit_test.py`

- Beside `test_suspicious_is_ok_not_verified` (`:194`): a report with `collected=4` and `deselected=3` gives `status == "ok"`, and the summary contains `Collected 1 tests` and `Not verified`. Set `report.summary.deselected = 3` on `_report(4)`. This covers `toolkit.py:215`.
