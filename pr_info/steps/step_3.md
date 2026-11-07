# Step 3 — mypy: errors-only findings, `raw` = mypy's raw output

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_3.md`.
> Write the tests first, then the implementation. Run pylint, mypy and pytest
> (`extra_args=["-n", "auto", "-m", "not integration"]`), format the code, and
> make exactly one commit.

## WHERE

- `src/mcp_tools_py/toolkit_checks.py` — `_run_mypy`
- `tests/test_toolkit_check_mypy.py`

## WHAT

`_run_mypy(context, depth) -> ActionResult` — signature unchanged.

## HOW

Two edits in `_run_mypy`:

1. `issues = [m for m in result.messages if m.severity == "error"]`
2. final `replace(...)`: `raw=result.raw_output or ""`

Update the docstring ("one Finding per error message"; raw is mypy's raw
output, empty when the runner returned early, e.g. on a timeout).

## ALGORITHM

```
issues = messages with severity == "error"
findings / fix_text built from issues as today
result = _result_from_findings(...)
return replace(result, fix_text=fix_text, raw=result.raw_output or "")
```

## DATA

Notes only → `status="ok"`, no findings, `raw` holds the raw output (notes
remain visible there).

## Tests (write first)

In `tests/test_toolkit_check_mypy.py`, `TestStatusSummaryRaw.test_run_kinds`:
rework the `raw` column so it reflects `raw_output`, not error/stderr:

- give the cases a `raw_output=` value (e.g. `"mypy raw text"`) and expect
  `raw == raw_output`;
- `rc1-notes-only`: `raw_output` contains the note text → status `"ok"`,
  `raw` equals it (the notes-only case the issue asks for);
- `new-failure` with `raw_output=` set → `raw` equals it.

`test_timeout_keeps_newlines_and_advice`: `raw == ""` (timeouts have no raw
output); summary unchanged.

Add `test_warning_severity_is_not_a_finding` in `TestFindings`: a message with
`severity="warning"` alongside an error → only the error is a finding.
