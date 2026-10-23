# Step 2 — Register deptry as a `python -m` tool

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_2.md`. Write the tests first, then the code. Run the checks listed in the summary and commit once.

## WHERE

- `pyproject.toml`
- `src/mcp_tools_py/utils/environment_info.py`
- `src/mcp_tools_py/utils/project_config.py`
- `tests/test_environment_info.py`, `tests/test_project_config.py`

## WHAT

- `pyproject.toml` `[project] dependencies`: add `"deptry>=0.25.1"` after `"mypy>=1.13.0"`.
- `TOOL_MODULES`: add `"deptry": "deptry"` after `"mypy"`.
- `ToolName` literal: add `"deptry"`.

## HOW

Nothing else is needed. `PROBED_MODULES` and `TOOL_DISTRIBUTIONS` are derived from `TOOL_MODULES`. `ToolContext.is_tool_available` / `unavailable_message` handle every non-console-script tool through the probe. `CONSOLE_SCRIPT_TOOLS` stays at seven entries. The fake probe in `tests/conftest.py` already reports every `PROBED_MODULES` entry as importable.

Update the `_failed` docstring in `environment_info.py` ("all three module tools" becomes "all four"). The rest of the wording changes are in step 7.

## DATA

- `PROBED_MODULES == ("pytest", "pylint", "mypy", "deptry")`
- `"deptry" in TOOL_DISTRIBUTIONS`

## Tests (write first)

- `tests/test_environment_info.py`: `"deptry"` is in `PROBED_MODULES` and in `TOOL_DISTRIBUTIONS`, and `TOOL_MODULES["deptry"] == "deptry"`.
- `tests/test_project_config.py`: `get_check_timeout(project, "deptry")` reads `[tool.mcp-tools-py] deptry-timeout`, and defaults to 120 when unset.
