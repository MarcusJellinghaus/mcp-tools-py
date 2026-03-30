# Step 3: `FormatterTools` class + MCP tool registration + tests

> **Context**: See [summary.md](summary.md) for full issue context.

## Goal

Create the `FormatterTools` class that registers the `run_format_code` MCP tool. This is the orchestration layer that validates inputs, resolves directories, calls runners in order, and assembles output.

## WHERE

| Action | File |
|--------|------|
| Create | `src/mcp_tools_py/formatter/formatter_tools.py` |
| Modify | `src/mcp_tools_py/formatter/__init__.py` (add re-export of `FormatterTools`) |
| Create | `tests/test_formatter_tools.py` |

## WHAT — Class and method signatures

```python
# src/mcp_tools_py/formatter/formatter_tools.py

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_tools_py.server import FastMCPProtocol, ToolServer


_VALID_STEPS = {"isort", "black"}

_STEP_RUNNERS: dict[str, Callable] = {
    "isort": run_isort,
    "black": run_black,
}


class FormatterTools:
    """Registers formatting tools on an MCP server."""

    def __init__(self, server: "ToolServer") -> None:
        self._server = server

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all formatter tools with the MCP server."""
        self._register_format_code(mcp)

    def _register_format_code(self, mcp: "FastMCPProtocol") -> None:
        @mcp.tool()
        @log_function_call
        def run_format_code(
            steps: list[str] | None = None,
            target_directories: list[str] | None = None,
            check_only: bool = False,
        ) -> str:
            """Run code formatters (black, isort) on the project."""
            ...
```

## HOW — Integration

- Same pattern as `CheckerTools`: takes server ref, registers via `@mcp.tool()` + `@log_function_call`
- Uses `get_target_directories()` from `utils/project_config` when `target_directories` is None
- Uses `run_black()` and `run_isort()` from sibling runner modules
- Checks `_tool_availability` for each step before running
- `FormatterTools` re-exported from `formatter/__init__.py`

## ALGORITHM (pseudocode)

```
1. steps = steps or ["isort", "black"]
2. Validate all step names ∈ _VALID_STEPS, else raise ValueError
3. If target_directories is None: call get_target_directories(project_dir)
4. For each step in steps:
   a. Check _tool_availability[step] — if unavailable, return error immediately
   b. runner = _STEP_RUNNERS[step]
   c. (output, success) = runner(python_executable, dirs, project_dir, check_only)
   d. Append "## {step}\n{output}" to sections
   e. Normal mode + not success → stop, return collected output + error note
   f. check_only mode + not success → continue (non-zero = "needs formatting", not error)
      BUT if execution_error (crash/missing tool) → stop
5. Return joined sections
```

## DATA — Return value examples

```
## isort
Fixing src/mcp_tools_py/server.py

## black
reformatted src/mcp_tools_py/server.py

All done! 1 file reformatted, 5 files left unchanged.
```

Error case (normal mode, black fails):
```
## isort
Fixing src/mcp_tools_py/server.py

## black
error: cannot format src/bad_file.py: Cannot parse: 1:0

Formatting stopped due to errors in black step.
```

## TESTS — `tests/test_formatter_tools.py`

1. **test_registers_one_tool** — verify `mcp.tool()` called exactly once
2. **test_default_steps_isort_then_black** — call with no args, verify isort runs before black
3. **test_custom_steps_order** — pass `steps=["black"]`, verify only black runs
4. **test_invalid_step_raises_error** — pass `steps=["ruff"]`, verify error returned (not exception, string with error)
5. **test_target_directories_auto_detected** — mock `get_target_directories`, verify it's called when `target_directories=None`
6. **test_target_directories_explicit** — pass explicit dirs, verify `get_target_directories` NOT called
7. **test_check_only_runs_all_steps_despite_nonzero** — isort returns `success=False` (needs formatting), black still runs
8. **test_normal_mode_stops_on_first_failure** — isort returns `success=False`, black does NOT run
9. **test_output_has_markdown_headers** — verify output contains `## isort` and `## black`
10. **test_tool_unavailable_returns_error** — black not in `_tool_availability`, verify error message

## LLM Prompt

```
Implement Step 3 of issue #10 (see pr_info/steps/summary.md and pr_info/steps/step_3.md).

Create `src/mcp_tools_py/formatter/formatter_tools.py` with the `FormatterTools` class.
Update `src/mcp_tools_py/formatter/__init__.py` to re-export it.
Write tests first in `tests/test_formatter_tools.py`, then implement.

Follow the same registration pattern as CheckerTools in checker_tools.py.
The key orchestration logic: validate steps, resolve dirs, loop runners, handle errors.

Note: At this stage, do NOT modify server.py yet — that's Step 4. The FormatterTools class
should be ready to be wired in, but tests use a mock server (same pattern as test_checker_tools.py).

Run pylint, mypy, and pytest checks after implementation. Commit when all pass.
```
