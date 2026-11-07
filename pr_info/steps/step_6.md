# Step 6 — Depth-based pytest timeouts

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_6.md`.
> Write the tests first, then the implementation. Run pylint, mypy and pytest
> (`extra_args=["-n", "auto", "-m", "not integration"]`), then run
> `tests/test_toolkit_saved_coverage.py::test_malformed_timeout_leaves_no_temp_dir`
> explicitly (its module is marked `integration`). Format the code and make
> exactly one commit.

## WHERE

- `src/mcp_tools_py/toolkit.py` — `_run_test`, new constant
- `tests/test_toolkit_test.py`

## WHAT

```python
_LONG_TEST_TIMEOUT = 1800  # seconds; test@standard, @unattended and @full
```

## HOW

At the top of `_run_test` (after the pytest availability check):

```python
if depth != "quick":
    context = replace(context, check_timeout=_LONG_TEST_TIMEOUT)
```

`ToolContext.check_timeout` is the `cli_timeout` slot of
`get_check_timeout`, which ranks below `[tool.mcp-tools-py] pytest-timeout`
and `check-timeout`, so project settings still win. Do **not** use
`resolve_timeout`'s `explicit` argument (it outranks them). `replace()` reads
no config, so `mkdtemp` still runs before the first `resolve_timeout` call and
`test_malformed_timeout_leaves_no_temp_dir` keeps its order. Import
`replace` from `dataclasses`. Mention the timeout in `_run_test`'s docstring.

## ALGORITHM

```
if depth != "quick": context = replace(context, check_timeout=1800)
... unchanged: every context.resolve_timeout("pytest") now resolves
    explicit(None) -> pytest-timeout -> check-timeout -> 1800 -> 300
```

## DATA

`timeout_seconds` passed to `check_code_with_pytest` (and, for `full`, to
`start_coverage_run`).

## Tests (write first)

In `tests/test_toolkit_test.py`, new class `TestRunTestTimeout`, patching
`mcp_tools_py.toolkit.check_code_with_pytest` with a PASSED result
(`make_pytest_results(RunStatus.PASSED, test_results=_report(1, passed=1), summary_text=...)`)
and reading `timeout_seconds` from the mock's call kwargs:

- parametrized `standard`, `unattended` → 1800;
- `quick` → 300;
- `pytest-timeout = 42` in `[tool.mcp-tools-py]` at `standard` → 42;
- `check-timeout = 77` at `standard` → 77;
- `full` on `_write_coverage_project` (skip if `pytest_cov` missing): also patch
  `mcp_tools_py.toolkit.start_coverage_run` / `finish_coverage_run` as needed;
  both `check_code_with_pytest` and `start_coverage_run` receive 1800.
