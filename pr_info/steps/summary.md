# Summary — Add `run_deptry_check` tool (#251)

## Goal

A new MCP tool `run_deptry_check` that runs [deptry](https://github.com/fpgmaas/deptry) on the project. deptry compares the declared dependencies with the imports in the code and reports `DEP001`–`DEP005`. The toolkit's `check` action at `full` depth runs it too.

## Architectural / design changes

- **A fourth `python -m` tool.** deptry reads distribution metadata and the stdlib list from the interpreter that runs it, so it runs in the **project env** (`<project python> -m deptry`), the way pytest, pylint and mypy do. Adding `"deptry": "deptry"` to `TOOL_MODULES` is enough to put it in the environment probe (`PROBED_MODULES`, `TOOL_DISTRIBUTIONS`). Availability and the "not available" message then work with no further code. The console-script tools stay at seven, and the `python -m` tools go from three to four.
- **A source-only default target.** This is the first checker whose default targets **exclude test paths**. Otherwise every test-only import would be reported as DEP004. The logic in `resolve_coverage_source` becomes a neutral function, `resolve_source_directories`. `resolve_coverage_source` turns into a thin wrapper that keeps its existing wording, so the coverage wording never appears in deptry output.
- **A new checker package, `code_checker_deptry`, with two modules:**
  - `runners.py` holds the data model (`DeptryMessage`, `DeptryResult`), the strict JSON parser and `run_deptry_check_impl`. The result is structured and shared by the MCP tool and the toolkit, like `BanditResult`.
  - `reporting.py` holds the ruff/pylint-style digest built on `utils/report_counts`.
- **Strict result rule.** deptry writes its JSON report (`--json-output`) to a temp dir, which is always deleted. Only exit 0 or 1 **together with** a JSON file that exists and parses counts as a result. Anything else is an error with a stderr snippet. This covers deptry's crash-after-report exit 1.
- **No config added.** deptry runs with `cwd=project_dir` and reads the project's own `pyproject.toml` / `[tool.deptry]`. `extra_args` is passed through. Only the output flags `--json-output`, `--json-output=…` and `-o` are rejected.
- **Toolkit.** `check` → `full` gains deptry, both in `_CHECK_DEPTHS` / `_CHECK_RUNNERS` and in `llm_permissions`. It produces one `Finding` per deptry entry, keyed `file|code|module`. `verify()` is unchanged.
- **Timeouts.** `"deptry"` joins the `ToolName` literal, so `[tool.mcp-tools-py] deptry-timeout` works and the tool accepts `timeout_seconds`.
- **Runtime dependency.** `deptry>=0.25.1` is added to `dependencies`, like pytest, pylint and mypy.

## Files created

- `src/mcp_tools_py/code_checker_deptry/__init__.py`
- `src/mcp_tools_py/code_checker_deptry/runners.py`
- `src/mcp_tools_py/code_checker_deptry/reporting.py`
- `src/mcp_tools_py/checker_tools/deptry_tool.py`
- `tests/test_code_checker_deptry/__init__.py`
- `tests/test_code_checker_deptry/test_runners.py`
- `tests/test_code_checker_deptry/test_reporting.py`
- `tests/test_code_checker_deptry/test_tool.py`

## Files modified

- `pyproject.toml` — `deptry>=0.25.1` dependency
- `src/mcp_tools_py/utils/project_config.py` — `resolve_source_directories`, `ToolName`
- `src/mcp_tools_py/utils/environment_info.py` — `TOOL_MODULES`, `_failed` docstring
- `src/mcp_tools_py/utils/tool_context.py` — docstrings (three/four `python -m` tools)
- `src/mcp_tools_py/checker_tools/__init__.py` — registration
- `src/mcp_tools_py/toolkit_checks.py` — `_run_deptry`, `_CHECK_DEPTHS`, `_CHECK_RUNNERS`
- `src/mcp_tools_py/toolkit.py` — `full` permissions, `check_instructions`
- `src/mcp_tools_py/server.py` — docstring
- `src/mcp_tools_py/main.py` — parser description
- `.importlinter`, `tach.toml` — new package
- `README.md`, `docs/pyproject-configuration.md`, `docs/architecture/architecture.md`
- `tests/test_project_config.py`, `tests/test_environment_info.py`, `tests/test_checker_tools.py`, `tests/test_toolkit.py`, `tests/test_toolkit_check.py`

## Steps

1. `resolve_source_directories` (source dirs without test paths)
2. Register deptry as a `python -m` tool (probe, `ToolName`, dependency)
3. `code_checker_deptry/runners.py`: model, parser, runner, and import contracts
4. `code_checker_deptry/reporting.py`: the digest
5. MCP tool `run_deptry_check` and its registration
6. Toolkit `check` → `full`
7. Docs and wording

## Checks for every step

After each step, run pylint, mypy, `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`, lint-imports and ruff check, then `run_format_code`. All must pass. Each step is one commit.
