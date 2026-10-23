# Step 5 — MCP tool `run_deptry_check`

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_5.md`. Write the tests first, then the code. Use `checker_tools/bandit_tool.py` (structure, error handling) and `checker_tools/mypy_tool.py` (availability, `timeout_seconds`) as models. Run the checks listed in the summary and commit once.

## Precondition

The integration test runs real deptry, so deptry must be installed in the project env. Check with `mcp__mcp-tools-py__get_library_source("deptry")`. If it is not found, write one line to `pr_info/.blocked.txt` (`deptry is not installed in the project env; reinstall with the new dependency`) and stop.

## WHERE

- `src/mcp_tools_py/checker_tools/deptry_tool.py` (new)
- `src/mcp_tools_py/checker_tools/__init__.py`: import `deptry_tool`, call `deptry_tool.register(mcp, self)` after bandit, and add deptry to the class docstring.
- `tests/test_code_checker_deptry/test_tool.py` (new)
- `tests/test_checker_tools.py`: a timeout pass-through test, next to the bandit one (around line 187).

## WHAT

```python
def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None:
    @mcp.tool()
    @log_function_call
    def run_deptry_check(
        target_directories: list[str] | None = None,
        extra_args: list[str] | None = None,
        max_issues: int = 1,
        timeout_seconds: int | None = None,
    ) -> str: ...
```

Docstring:
- The tool runs deptry in the project env and reads `[tool.deptry]`.
- `target_directories` defaults to the source directories from pyproject.toml, excluding test paths.
- `extra_args` rejects `--json-output`, `--json-output=…` and `-o`.
- `max_issues` uses the ruff wording.
- `timeout_seconds` uses the mypy wording, with the default 120.

## HOW

Imports: `resolve_source_directories` from `utils.project_config`, `run_deptry_check_impl` from `code_checker_deptry.runners`, and `format_deptry_report` from `code_checker_deptry.reporting`.

## ALGORITHM

```
if not context.is_tool_available("deptry"): return context.unavailable_message("deptry")
resolved = resolve_source_directories(project_dir, target_directories); if str: return it
try: timeout = context.resolve_timeout("deptry", timeout_seconds) except ValueError as exc: return f"Error: {exc}"
result = run_deptry_check_impl(str(context.environment.interpreter), project_dir, resolved, extra_args, timeout)
if result.error: return f"deptry error: {result.error}"
return format_deptry_report(result.messages, max_issues) or "No deptry dependency issues found."
```

Wrap the run in the same `try/except Exception` with logging as `bandit_tool.py`, returning `"Unexpected error running deptry: <type>: <e>"`.

## DATA

The report string, the clean message, or an error string.

## Tests (write first)

`tests/test_code_checker_deptry/test_tool.py` uses a `_register_and_capture` helper copied from the bandit integration tests and the `tool_context` fixture. Patch `mcp_tools_py.checker_tools.deptry_tool.run_deptry_check_impl` for:
- **unavailable**: patch `ToolContext.is_tool_available` to return False for `"deptry"` → the result contains `"deptry is not available"`
- findings → the report contains `DEP001` and the file
- an error result → `"deptry error: ..."`
- clean → `"No deptry dependency issues found."`
- the default targets come from `resolve_source_directories`, so `tests` is excluded: write a `pyproject.toml` with `where=["src"]` and `testpaths=["tests"]` in `tool_context.project_dir`, and assert the captured `target_directories == ["src"]`
- explicit `target_directories` are passed through
- an invalid `timeout_seconds=0` → `"Error: ..."`

One `@pytest.mark.integration` test runs real deptry against a `tmp_path` project with `PythonEnvironment.resolve()`:
- `pyproject.toml` has `[project] name="p" version="0" dependencies=[]`, and `src/p/mod.py` contains `import os` → the clean message
- adding `import some_undeclared_pkg_xyz` → `DEP001` appears

`tests/test_checker_tools.py`: the resolved timeout (`timeout_seconds=7`) is passed to `run_deptry_check_impl`.
