# Step 1 — `run` returns `error` for an undeclared action or depth

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_1.md`.
> Write the tests first, then the implementation. Run pylint, mypy and pytest
> (`extra_args=["-n", "auto", "-m", "not integration"]`), format the code, and
> make exactly one commit.

## Precondition

Use `get_library_source("mcp_coder_utils.toolkit.Toolkit.verify")`. If its
signature has no `action` parameter, the implement venv has a stale
`mcp-coder-utils`: write one line to `pr_info/.blocked.txt` and stop.

## WHERE

- `src/mcp_tools_py/toolkit.py` — `PythonToolkit.run`
- `tests/test_toolkit_test.py` — `TestRunTest`

## WHAT

```python
def run(self, request: ActionRequest) -> ActionResult: ...
```

No new functions.

## HOW

Validate against `self.describe().actions` at the top of `run`, **before**
`_build_context` (which can raise). Keep the `test` and `format` branches;
after them, `return _run_check(context, request.depth)` unconditionally (the
action is known to be `check` by then) and delete
`raise NotImplementedError`. Update the docstring: no `Raises:` section; say
undeclared actions/depths return status `"error"`.

## ALGORITHM

```
depths = self.describe().actions.get(request.action)
if depths is None:
    return error("Unknown action 'x'; declared: format, check, test.")
if request.depth not in depths:
    return error("Unknown depth 'y' for action 'x'; declared: a, b, c.")
context = _build_context(request.project_dir)
dispatch to _run_test / _run_format / _run_check as today
```

## DATA

`ActionResult(status="error", summary=<one line naming the bad value and the declared values>)`, no findings.

## Tests (write first)

In `tests/test_toolkit_test.py`, `TestRunTest`:

- Replace `test_unknown_action_raises` with `test_unknown_action_is_error`:
  status `"error"`, `"bogus"` in the summary.
- `test_undeclared_depth_is_error`, parametrized over
  `("test", "bogus")`, `("format", "quick")`, `("check", "apply")`:
  patch `mcp_tools_py.toolkit._build_context` with
  `side_effect=AssertionError` (proves the check happens before it) and assert
  status `"error"` and the depth in the summary.
