# Step 4 — Toolkit `verify()` rows for pytest-json-report and pytest-cov

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_4.md`).
> Step 1 (`ToolContext.is_distribution_available`) is already done.
> Implement only this step, test first. Then run `run_format_code`, pylint, mypy and
> pytest (`extra_args=["-n", "auto", "-m", "not integration"]`); all must pass.
> This step is exactly one commit.

## WHERE

- `src/mcp_tools_py/toolkit.py`
- `tests/test_toolkit_verify.py`

## WHAT

```python
_PYTEST_COV_NOTE = (
    "pytest-cov is not installed in the project environment; "
    "only the `full` test depth needs it."
)

def _distribution_items(context: ToolContext) -> list[VerifyItem]: ...
```

In `PythonToolkit.verify`:

```python
distribution_items = _distribution_items(context) if action in (None, "test") else []
return [_tool_item(context, tool) for tool in tools] + distribution_items + formatter_items
```

Update the `verify` docstring bullets: `None` → every tool, pytest-json-report,
pytest-cov, plus "formatter"; `"test"` → pytest, pytest-json-report, pytest-cov.

## ALGORITHM

```
json_ok = context.is_distribution_available("pytest-json-report")
cov_ok = context.is_distribution_available("pytest-cov")
return [
    VerifyItem("pytest-json-report", "ok" if json_ok else "error",
               "" if json_ok else context.unavailable_message("pytest-json-report")),
    VerifyItem("pytest-cov", "ok" if cov_ok else "warning", "" if cov_ok else _PYTEST_COV_NOTE),
]
```

## DATA

`VerifyItem` statuses: `"ok"`, `"error"`, `"warning"` (all allowed by `VerifyStatus`).
Probe failure → both `"ok"` (fail open, via `distribution_available`).

## Tests (write first) — `tests/test_toolkit_verify.py`

Add `_GET_ENVIRONMENT_INFO = "mcp_tools_py.utils.tool_context.get_environment_info"` and
`_BOTH = make_environment_info(distributions={"pytest-json-report": "1.5.0", "pytest-cov": "7.1.0"})`.

1. `test_healthy_environment_is_all_ok`: patch the probe with `_BOTH`; expect 14 items, all
   `ok`, names = the existing 12 plus `"pytest-json-report"`, `"pytest-cov"`.
2. `test_test_reports_pytest`: patch with `_BOTH`; names ==
   `{"pytest", "pytest-json-report", "pytest-cov"}`.
3. New, parametrized over action `None` and `"test"`:
   - `distributions={}` → `pytest-json-report` row `error`, message contains
     `"pytest-json-report is not available"`; `pytest-cov` row `warning`, message
     contains `"full"`.
   - broken probe (`EnvironmentInfo(..., error="boom")`) → both rows `ok`.
4. Existing `"check"` / `"format"` tests stay unchanged (their exact name sets prove the
   rows are absent there).

If `src/mcp_tools_py/toolkit.py` exceeds 750 lines after this step, write one line to
`pr_info/.blocked.txt` and stop.
