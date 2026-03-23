# Step 1: Scaffolding + Dependencies

**Commit:** `feat: add dependencies and scaffold refactoring module (#108)`

**Context:** See `pr_info/steps/summary.md` for full issue context and architecture overview.

**Goal:** Add rope/jedi dependencies, create the refactoring module skeleton, update architecture config (tach.toml, .importlinter, .gitignore), and rename the architecture layer. No new tool logic yet. No changes to server.py in this step.

---

## LLM Prompt

> **Task:** Implement Step 1 of Issue #108 (Add Python refactoring tools).
> Read `pr_info/steps/summary.md` for full context, then follow `pr_info/steps/step_1.md` exactly.
>
> Create the `refactoring/` module skeleton with `RefactoringTools`.
> Add dependencies. Rename architecture layer. Update `.gitignore`.
> All existing tests must continue to pass.

---

## Part A: Refactoring module skeleton

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

## Part B: Architecture & config updates

### WHERE & WHAT

**`pyproject.toml`** — add to `dependencies`:
```toml
"rope>=1.13.0",
"jedi>=0.19.0",
```

**`pyproject.toml`** — register the `integration` marker to prevent `PytestUnknownMarkWarning` (required if `--strict-markers` is ever enabled):
```toml
[tool.pytest.ini_options]
markers = [
    "integration: Integration tests requiring external resources",
]
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
3. **Do NOT change `mcp_tools_py.server` depends_on in this step.** Keep server's current dependencies on `code_checker_*` modules intact. The dependency swap (removing `code_checker_*` and adding `checker_tools` + `refactoring`) is deferred to Step 2, when `checker_tools.py` actually exists and `server.py` is modified. This ensures `tach_check` passes after Step 1.

**`.importlinter`** — changes:
1. Rename layer `checker_implementation` → `tool_implementation`
2. Add `mcp_tools_py.checker_tools` and `mcp_tools_py.refactoring` to the layers contract at the same level as existing checker modules. The exact layer ordering must be:
```
mcp_tools_py.main
mcp_tools_py.server
mcp_tools_py.checker_tools | mcp_tools_py.refactoring | mcp_tools_py.code_checker_pytest | mcp_tools_py.code_checker_pylint | mcp_tools_py.code_checker_mypy
mcp_tools_py.utils
mcp_tools_py.log_utils
```
3. Add `mcp_tools_py.checker_tools` and `mcp_tools_py.refactoring` to the forbidden-imports contract (utils cannot import them)

> **Note:** The pipe-separated format (`module_a | module_b`) declares modules at the same layer level. After editing `.importlinter`, immediately run `lint-imports` to verify the syntax works. If the pipe syntax isn't supported by the installed version, list each module on a separate line but note that import-linter treats adjacent entries as ordered layers — which would incorrectly constrain the checker/refactoring modules.

**`.gitignore`** — add:
```
# Rope project cache
.ropeproject/
```

---

## Verification Checklist

1. All existing tests pass (no behavior change)
2. `tach_check` passes with renamed layer
3. `lint_imports` passes with updated contracts
4. pylint, mypy pass on new files
