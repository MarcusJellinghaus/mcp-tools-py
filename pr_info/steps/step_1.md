# Step 1: Scaffolding + Server Refactor

**Commit:** `feat: extract CheckerTools and scaffold refactoring module (#108)`

**Context:** See `pr_info/steps/summary.md` for full issue context and architecture overview.

**Goal:** Extract existing checker tool registrations from `server.py` into a `CheckerTools` class, rename the architecture layer, add dependencies, create the refactoring module skeleton, and verify all existing tests still pass. No new tool logic yet.

---

## LLM Prompt

> **Task:** Implement Step 1 of Issue #108 (Add Python refactoring tools).
> Read `pr_info/steps/summary.md` for full context, then follow `pr_info/steps/step_1.md` exactly.
>
> Extract checker tool registrations from `server.py` into a new `CheckerTools` class.
> Create the `refactoring/` module skeleton with `RefactoringTools`.
> Rename architecture layer. Add dependencies. Update `.gitignore`.
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

### DATA
- `CheckerTools` holds a reference to `CodeCheckerServer` instance
- No new data structures — same inputs/outputs as before

---

## Part C: Refactoring module skeleton

### WHERE
- `src/mcp_tools_py/refactoring/__init__.py` (new)
- `src/mcp_tools_py/refactoring/jedi_tools.py` (new, empty placeholder)
- `src/mcp_tools_py/refactoring/rope_tools.py` (new, empty placeholder)
- `tests/test_refactoring/__init__.py` (new)

### WHAT — `refactoring/__init__.py`
```python
"""Python refactoring tools powered by rope and jedi."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_tools_py.server import FastMCPProtocol


class RefactoringTools:
    """Registers refactoring tools on an MCP server."""

    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir

    def register(self, mcp: "FastMCPProtocol") -> None:
        """Register all refactoring tools. (No tools registered yet.)"""
        pass
```

### WHAT — placeholder files
```python
# jedi_tools.py
"""Jedi-based symbol discovery and reference finding."""

# rope_tools.py
"""Rope-based refactoring operations (move, rename)."""
```

---

## Part D: Architecture & config updates

### WHERE & WHAT

**`pyproject.toml`** — add to `dependencies`:
```toml
"rope>=1.13.0",
"jedi>=0.19.0",
```

**`tach.toml`** — changes:
1. Rename layer `checker_implementation` → `tool_implementation`
2. Add new modules:
```toml
[[modules]]
path = "mcp_tools_py.checker_tools"
layer = "tool_implementation"
depends_on = [
    { path = "mcp_tools_py.code_checker_pytest" },
    { path = "mcp_tools_py.code_checker_pylint" },
    { path = "mcp_tools_py.code_checker_mypy" },
    { path = "mcp_tools_py.utils" },
    { path = "mcp_tools_py.log_utils" }
]

[[modules]]
path = "mcp_tools_py.refactoring"
layer = "tool_implementation"
depends_on = [
    { path = "mcp_tools_py.log_utils" }
]
```
3. Update `mcp_tools_py.server` depends_on: replace individual checker deps with `mcp_tools_py.checker_tools`, add `mcp_tools_py.refactoring`:
```toml
[[modules]]
path = "mcp_tools_py.server"
layer = "server"
depends_on = [
    { path = "mcp_tools_py.checker_tools" },
    { path = "mcp_tools_py.refactoring" },
    { path = "mcp_tools_py.utils" },
    { path = "mcp_tools_py.log_utils" }
]
```

**`.importlinter`** — changes:
1. Add `mcp_tools_py.checker_tools` and `mcp_tools_py.refactoring` to the layers contract (same level as existing checker modules — between server and utils)
2. Add both to forbidden-imports contract (utils cannot import them)

**`.gitignore`** — add:
```
# Rope project cache
.ropeproject/
```

---

## Verification Checklist

1. All existing tests pass (no behavior change)
2. `test_checker_tools.py` tests pass
3. `tach_check` passes with renamed layer
4. `lint_imports` passes with updated contracts
5. pylint, mypy pass on new files
