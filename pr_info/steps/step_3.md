# Step 3: Register `run_tach_check` MCP Tool + Update `tach.toml`

## LLM Prompt
> Read `pr_info/steps/summary.md` and `pr_info/steps/step_3.md`, then implement step 3. Update `tach.toml` first (declare new module + add to checker_tools.depends_on), then add `_register_tach` in `checker_tools.py` and call from `register()`. Run `mcp__tools-py__run_pylint_check`, `run_pytest_check`, `run_mypy_check`, and (manually) `tach check`; all must pass before commit.

## WHERE

Modify:
- `src/mcp_tools_py/checker_tools.py` — import `run_tach_check`, add `_register_tach()` method, call from `register()`, update class docstring.
- `tach.toml` — add new `[[modules]]` entry and update `mcp_tools_py.checker_tools.depends_on`.
- `tests/test_checker_tools.py` — add tach to `mock_server` fixture, update registration count test, add tach handler tests.

## WHAT

### `tach.toml`

Add new module entry (alongside the other checker modules):

```toml
[[modules]]
path = "mcp_tools_py.code_checker_tach"
layer = "tool_implementation"
depends_on = [
    { path = "mcp_tools_py.utils" },
    { path = "mcp_tools_py.log_utils" }
]
```

Add `mcp_tools_py.code_checker_tach` to the existing `mcp_tools_py.checker_tools.depends_on` list.

### `checker_tools.py`

Add import:
```python
from mcp_tools_py.code_checker_tach import run_tach_check as run_tach
```

Add method `_register_tach(self, mcp)` and call it from `register()`:

```python
@mcp.tool()
@log_function_call
def run_tach_check() -> str:
    """Run tach check on the project to validate architectural boundaries.

    Returns:
        Status line followed by raw JSON output from `tach check --output json`.
    """
    if not self._server._is_tool_available("tach"):
        binary_path = self._server._tach_binary or "N/A"
        return (
            f"tach is not available at {binary_path}. "
            f"Ensure the virtual environment has tach installed "
            f"and --venv-path is configured. Restart the server after installing."
        )

    try:
        logger.info(
            "Starting tach check",
            extra={"project_dir": str(self._server.project_dir)},
        )
        binary = self._server._tach_binary
        assert binary is not None
        output = run_tach(
            tach_binary=binary,
            project_dir=str(self._server.project_dir),
        )
        logger.info("tach check completed", extra={"output_length": len(output)})
        return output
    except Exception as e:
        error_msg = f"Unexpected error running tach: {type(e).__name__}: {e}"
        logger.error(
            "tach check failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "project_dir": str(self._server.project_dir),
            },
        )
        return error_msg
```

## HOW

- Pattern mirrors `_register_lint_imports` and `_register_vulture`.
- Zero parameters on the tool (issue requirement).
- `register()` adds `self._register_tach(mcp)` after `self._register_bandit(mcp)`.
- The `CheckerTools` class docstring (around line 49 of `src/mcp_tools_py/checker_tools.py`) currently reads `"Registers pylint, pytest, mypy, lint-imports, vulture, ruff, and bandit checker tools on an MCP server."` — it omits the ruff fix variant and is becoming stale. Replace it with one that lists all 9 tools accurately, e.g.: `"Registers pylint, pytest, mypy, lint-imports, vulture, ruff check, ruff fix, bandit, and tach checker tools on an MCP server."`

## ALGORITHM

Tool handler logic:
```
if not _is_tool_available("tach"): return error string with binary path
log "Starting tach check"
output = run_tach(binary, project_dir)
log "tach check completed"
return output  # error message on exception, output otherwise
```

## DATA

- Returns `str` (status line + JSON, fallback message, or error message).

## Tests

Update `tests/test_checker_tools.py`:

1. **Registration count test** — `test_checker_tools_registers_eight_tools` currently asserts `mock_mcp.tool.call_count == 8`. With tach added, this becomes 9. Update the assertion AND rename the test (e.g., `test_checker_tools_registers_nine_tools`). Also update the in-test comment listing the registered tools.

2. **`mock_server` fixture** — add `"tach": True` to the `_tool_availability` dict and `server._tach_binary = "/mock/venv/bin/tach"` (mirroring the existing `_vulture_binary` style).

3. **Handler tests** — add two tests mirroring `test_vulture_unavailable_returns_error` and `test_vulture_success_returns_raw_output`:
   - `test_tach_unavailable_returns_error` — set `mock_server._tool_availability["tach"] = False`; capture `run_tach_check`; assert returned string contains `"tach is not available"`.
   - `test_tach_success_returns_raw_output` — patch `mcp_tools_py.checker_tools.run_tach` (the alias used in the import) to return a fake string; invoke the captured tool; assert the patched runner was called with the expected `tach_binary` and `project_dir` kwargs and the return value matches.

(No changes to `test_tool_availability.py` beyond what step 2 already covers.)

(Optional sanity check: verify `tach check` on the project itself succeeds after the `tach.toml` update — done outside test suite via `tools/tach_check.sh`.)

## Acceptance

- `run_pytest_check` (fast unit run) — all pass, including the updated `tests/test_checker_tools.py` (renamed registration count test + new tach handler tests).
- `run_pylint_check`, `run_mypy_check` — clean.
- `tach check` on the project — passes with the new module declared and listed in `checker_tools.depends_on`.
- One commit: tach.toml + checker_tools.py + test_checker_tools.py.
