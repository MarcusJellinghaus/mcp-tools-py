# Step 4: Server rename + wiring (all integration changes)

> **Context**: See [summary.md](summary.md) for full issue context.

## Goal

Rename `CodeCheckerServer` → `ToolServer`, wire up `FormatterTools`, add `black`/`isort` to tool availability, move deps to main, update `tach.toml`, and update all existing tests.

## WHERE

| Action | File |
|--------|------|
| Modify | `src/mcp_tools_py/server.py` |
| Modify | `src/mcp_tools_py/checker_tools.py` |
| Modify | `pyproject.toml` |
| Modify | `tach.toml` |
| Modify | `tests/test_tool_availability.py` |
| Modify | `.importlinter` |
| Modify | `tests/test_checker_tools.py` |

## WHAT — Changes per file

### `src/mcp_tools_py/server.py`

1. **Rename class**: `CodeCheckerServer` → `ToolServer`
2. **Rename FastMCP name**: `"Code Checker Service"` → `"MCP Tools Service"`
3. **Update docstrings**: class and `create_server()` return type
4. **Add import**: `from mcp_tools_py.formatter import FormatterTools`
5. **Register FormatterTools**: `FormatterTools(self).register(self.mcp)` after CheckerTools
6. **Add availability checks** for `black` and `isort` in `_check_tool_availability()`:
   ```python
   # Add to the existing loop:
   for tool in ["pytest", "pylint", "mypy", "black", "isort"]:
   ```

### `src/mcp_tools_py/checker_tools.py`

7. **Update TYPE_CHECKING import**: `CodeCheckerServer` → `ToolServer`

### `pyproject.toml`

8. **Move** `black>=24.10.0` and `isort>=5.13.2` from `[project.optional-dependencies] dev` to `[project] dependencies`

### `tach.toml`

9. **Add** `mcp_tools_py.formatter` module:
   ```toml
   [[modules]]
   path = "mcp_tools_py.formatter"
   layer = "tool_implementation"
   depends_on = [
       { path = "mcp_tools_py.utils" },
       { path = "mcp_tools_py.log_utils" }
   ]
   ```

10. **Update** `mcp_tools_py.server` depends_on to include `{ path = "mcp_tools_py.formatter" }`

### `.importlinter`

11. **Add** `mcp_tools_py.formatter` to the layers contract (piped with other tool_implementation modules):
    ```
    mcp_tools_py.checker_tools | mcp_tools_py.refactoring | mcp_tools_py.utility_tools | mcp_tools_py.inspect_library | mcp_tools_py.formatter
    ```

12. **Add** `mcp_tools_py.formatter -> mcp_tools_py.server` to `ignore_imports` (same pattern as checker_tools/refactoring/etc.)

13. **Add** `mcp_tools_py.formatter` to `forbidden_modules` in the forbidden-imports contract

### `tests/test_tool_availability.py`

14. **Update** `_create_server` reference (import stays the same — it imports from `mcp_tools_py.server`)
15. **Update** expected `_tool_availability` dicts to include `"black": True/False` and `"isort": True/False`
16. **Add tests**: `test_black_available`, `test_isort_available` (follow existing pattern)

### `tests/test_checker_tools.py`

17. **Update** `mock_server` fixture: add `"black": True, "isort": True` to `_tool_availability`

## ALGORITHM

No new algorithmic logic — this step is purely wiring existing pieces together.

The availability check for `black` and `isort` uses the same pattern as `pytest`/`pylint`/`mypy`:
```python
for tool in ["pytest", "pylint", "mypy", "black", "isort"]:
    result = execute_command([self._resolved_python, "-m", tool, "--version"], ...)
    availability[tool] = result.return_code == 0 and not result.execution_error
```

## DATA

Updated `_tool_availability` dict shape:
```python
{
    "pytest": bool,
    "pylint": bool,
    "mypy": bool,
    "lint-imports": bool,
    "vulture": bool,
    "black": bool,    # NEW
    "isort": bool,    # NEW
}
```

## LLM Prompt

```
Implement Step 4 of issue #10 (see pr_info/steps/summary.md and pr_info/steps/step_4.md).

This is the final wiring step. Make all changes listed in the step file:

1. Rename CodeCheckerServer → ToolServer in server.py (class, docstrings, create_server return type)
2. Change FastMCP name to "MCP Tools Service"
3. Add FormatterTools import and registration in server.__init__
4. Add black/isort to _check_tool_availability() loop (same pattern as pytest/pylint/mypy)
5. Update checker_tools.py TYPE_CHECKING import
6. Move black/isort from dev deps to main deps in pyproject.toml
7. Add formatter module to tach.toml, update server depends_on
8. Update .importlinter: add formatter to layers contract, ignore_imports, and forbidden_modules
9. Update all test files: new availability dict keys, class name references

Run pylint, mypy, and pytest checks. Fix any issues. Commit when all pass.
After committing, run ./tools/format_all.sh to ensure formatting is clean.
```
