# Step 1 — Distribution check on `ToolContext` + conftest default

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_1.md`).
> Implement only this step, test first. Then run `run_format_code`, pylint, mypy and
> pytest (`extra_args=["-n", "auto", "-m", "not integration"]`); all must pass.
> This step is exactly one commit.

## WHERE

- `src/mcp_tools_py/utils/tool_context.py`
- `tests/conftest.py`
- `tests/test_tool_context.py`

## WHAT

```python
# tool_context.py (module level)
def distribution_available(info: EnvironmentInfo, name: str) -> bool: ...

# ToolContext
def is_distribution_available(self, name: str) -> bool: ...
```

## HOW

- Import `EnvironmentInfo` from `mcp_tools_py.utils.environment_info` alongside the
  existing `get_environment_info` import.
- The method calls the `get_environment_info` bound in `tool_context.py` — the target
  that the conftest patch `mcp_tools_py.utils.tool_context.get_environment_info` covers.
- No logging (callers' `is_tool_available("pytest")` already logs a failed probe).
- Docstrings: `name` is a distribution name compared exactly against the probe's
  lowercased (not PEP 503 normalised) keys; a failed probe counts as available.
- Module docstring of `tool_context.py`: it says a registrar asks "the two questions"
  (is this tool there, what to say when it is not); add the third — is a distribution
  (pytest-json-report, pytest-cov) installed, answered by `is_distribution_available` —
  matching the architecture-doc wording in `step_7.md`.

## ALGORITHM

```
distribution_available(info, name):
    return info.error is not None or name in info.distributions

is_distribution_available(self, name):
    info = get_environment_info(str(self.environment.interpreter))
    return distribution_available(info, name)
```

## DATA

- Returns `bool`.
- `tests/conftest.py::make_environment_info`: when `distributions is None`, use
  `{"pytest-json-report": "1.5.0"}`; an explicit `{}` stays empty ("missing").
  Replace `distributions or {}` with
  `{"pytest-json-report": "1.5.0"} if distributions is None else distributions`
  and update the docstring.

## Tests (write first) — `tests/test_tool_context.py`

One parametrized test, patching `_GET_ENVIRONMENT_INFO` (already defined in the file),
using the existing `_context(tmp_path)` helper:

| case | probe | name | expected |
|---|---|---|---|
| installed | `make_environment_info()` | `"pytest-json-report"` | `True` |
| missing | `make_environment_info(distributions={})` | `"pytest-json-report"` | `False` |
| probe failed | `EnvironmentInfo(version="", sys_path=(), distributions={}, importable={}, error="boom")` | `"pytest-cov"` | `True` |
