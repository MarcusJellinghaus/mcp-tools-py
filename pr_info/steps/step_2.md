# Step 2: Register UtilityTools in server + update architecture configs

> **Context**: See [summary.md](summary.md) for full issue context.

## Commit message
`feat: register UtilityTools and update architecture configs`

## WHERE

| Action | File |
|--------|------|
| Modify | `src/mcp_tools_py/server.py` |
| Modify | `tach.toml` |
| Modify | `.importlinter` |

## WHAT

### `src/mcp_tools_py/server.py`

Two changes:
1. Add import: `from mcp_tools_py.utility_tools import UtilityTools`
2. Add registration line in `__init__`: `UtilityTools().register(self.mcp)`

Place after the existing `RefactoringTools` registration.

### `tach.toml`

Add new module entry:
```toml
[[modules]]
path = "mcp_tools_py.utility_tools"
layer = "tool_implementation"
depends_on = [
    { path = "mcp_tools_py.log_utils" }
]
```

Add dependency in the `server` module:
```toml
# In the existing server module's depends_on list, add:
{ path = "mcp_tools_py.utility_tools" }
```

### `.importlinter`

**Layered contract** — add `mcp_tools_py.utility_tools` to the tool_implementation tier:
```
mcp_tools_py.checker_tools | mcp_tools_py.refactoring | mcp_tools_py.utility_tools
```

**Forbidden imports contract** — add to the forbidden_modules list:
```
mcp_tools_py.utility_tools
```

## HOW

### Integration points
- `server.py` imports `UtilityTools` at module level (same as `CheckerTools`, `RefactoringTools`)
- `UtilityTools()` takes no constructor args (unlike `CheckerTools(self)` or `RefactoringTools(project_dir)`)
- Architecture enforcement tools (`tach check`, `import-linter`) will validate the new config

## DATA

No new data structures. The server just wires up the existing `UtilityTools.register()` method.

## LLM Prompt

```
Implement Step 2 of issue #116 (see pr_info/steps/summary.md and pr_info/steps/step_2.md).

Wire up the UtilityTools class created in Step 1:

1. In `src/mcp_tools_py/server.py`:
   - Add import: `from mcp_tools_py.utility_tools import UtilityTools`
   - Add `UtilityTools().register(self.mcp)` after the RefactoringTools registration line

2. In `tach.toml`:
   - Add a new [[modules]] block for mcp_tools_py.utility_tools (layer: tool_implementation, depends_on: log_utils only)
   - Add { path = "mcp_tools_py.utility_tools" } to the server module's depends_on list

3. In `.importlinter`:
   - Add mcp_tools_py.utility_tools to the layered contract (pipe-separated with checker_tools and refactoring)
   - Add mcp_tools_py.utility_tools to the forbidden_modules list in the forbidden-imports contract

4. Run all three code quality checks (pylint, mypy, pytest) and fix any issues.

5. Commit with message: "feat: register UtilityTools and update architecture configs"
```
