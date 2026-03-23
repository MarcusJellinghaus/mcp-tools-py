# Step 2: Extract CheckerTools from server.py

**Commit:** `refactor: extract CheckerTools from server.py (#108)`

**Context:** See `pr_info/steps/summary.md` for full issue context. Step 1 must be completed first (scaffolding and dependencies in place).

**Goal:** Extract existing checker tool registrations from `server.py` into a `CheckerTools` class, wire it into server.py, update tach.toml and .importlinter for the new checker_tools module, and verify all existing tests still pass. No new tool logic yet.

> **Note:** The CheckerTools closures reference `self._server` attributes (like `_resolved_python`) at call time, not definition time. This late-binding is correct — no ordering issue — but be aware that closures capture the server reference, not its current attribute values.

---

## LLM Prompt

> **Task:** Implement Step 2 of Issue #108 (Add Python refactoring tools).
> Read `pr_info/steps/summary.md` for full context, then follow `pr_info/steps/step_2.md` exactly.
>
> Extract checker tool registrations from `server.py` into a new `CheckerTools` class.
> Wire `CheckerTools` into `server.py`.
> Update `tach.toml` and `.importlinter` for the `checker_tools` module.
> Write tests first (TDD). All existing tests must continue to pass.

---

## Part A: Tests for CheckerTools extraction

### WHERE
- `tests/test_checker_tools.py` (new)

### WHAT
```python
# Test that CheckerTools registers 3 tools on an MCP server
def test_checker_tools_registers_three_tools():
    ...

# Test that formatting methods work identically to before
def test_format_pylint_result_no_issues():
    ...
def test_format_pylint_result_with_issues():
    ...
def test_format_mypy_result_no_issues():
    ...
def test_format_mypy_result_with_issues():
    ...
def test_format_pytest_result_success():
    ...
def test_format_pytest_result_failure():
    ...
```

### HOW
- Import `CheckerTools` from `mcp_tools_py.checker_tools`
- Test formatting methods directly (they are pure functions on the class)
- For registration test: create a mock/minimal FastMCP, call `register()`, verify 3 tools registered

---

## Part B: Extract CheckerTools class

### WHERE
- `src/mcp_tools_py/checker_tools.py` (new)
- `src/mcp_tools_py/server.py` (modify)

### WHAT — `checker_tools.py`
```python
class CheckerTools:
    """Registers pylint, pytest, and mypy checker tools on an MCP server."""

    def __init__(self, server: "CodeCheckerServer") -> None:
        self._server = server

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all checker tools with the MCP server."""
        # Move the 3 @mcp.tool() definitions here
        ...

    # Move these formatting methods here (unchanged):
    def _format_pylint_result(self, pylint_prompt: Optional[str]) -> str: ...
    def _format_pytest_result_with_details(self, test_results: dict, show_details: bool) -> str: ...
    def _format_mypy_result(self, mypy_prompt: str | None) -> str: ...
```

### WHAT — `server.py` changes
```python
# BEFORE:
class CodeCheckerServer:
    def __init__(self, ...):
        ...
        self._register_tools()
        ...

    def _format_pylint_result(self, ...): ...
    def _format_pytest_result_with_details(self, ...): ...
    def _format_mypy_result(self, ...): ...
    def _register_tools(self): ...  # ~300 lines of tool definitions

# AFTER:
from mcp_tools_py.checker_tools import CheckerTools

class CodeCheckerServer:
    def __init__(self, ...):
        ...
        CheckerTools(self).register(self.mcp)
        ...
    # No more _register_tools, no more _format_* methods
```

### ALGORITHM (CheckerTools.register)
```
1. Define run_pylint_check as closure, decorate with @mcp.tool() and @log_function_call
2. Define run_pytest_check as closure, decorate same way
3. Define run_mypy_check as closure, decorate same way
4. Each closure accesses self._server for project_dir, _resolved_python, _tool_availability, etc.
```

> **Late-binding note:** The closures capture `self._server` (the server reference), not its current attribute values. Attributes like `_resolved_python` are resolved at call time, not definition time. This is correct behavior — no ordering issue.

### DATA
- `CheckerTools` holds a reference to `CodeCheckerServer` instance
- No new data structures — same inputs/outputs as before

---

## Part C: Wire into server.py and update architecture config

### WHERE
- `src/mcp_tools_py/server.py` (modify)
- `tach.toml` (verify checker_tools entry from Step 1)
- `.importlinter` (verify checker_tools entry from Step 1)

### WHAT
- In `server.py`, replace `self._register_tools()` call with `CheckerTools(self).register(self.mcp)`
- Remove `_register_tools`, `_format_pylint_result`, `_format_pytest_result_with_details`, `_format_mypy_result` methods from `CodeCheckerServer`
- Verify `tach.toml` and `.importlinter` already have `checker_tools` entries (added in Step 1)

---

## Verification Checklist

1. All existing tests pass (no behavior change)
2. `test_checker_tools.py` tests pass
3. `tach_check` passes
4. `lint_imports` passes
5. pylint, mypy pass on new files
