# Step 3: Architecture Config Updates

> **Reference**: See `pr_info/steps/summary.md` for full context.

## Goal

Update `tach.toml` and `.importlinter` to include `inspect_library` in the architecture boundary enforcement, matching the patterns used by `checker_tools` and `refactoring`.

## LLM Prompt

```
Implement Step 3 of issue #101 (see pr_info/steps/summary.md for context).

Update architecture config files to include the new inspect_library module:

1. tach.toml:
   - Add mcp_tools_py.inspect_library module in tool_implementation layer, depends on log_utils
   - Add mcp_tools_py.inspect_library to server module's depends_on list

2. .importlinter:
   - Add mcp_tools_py.inspect_library to the layers contract alongside checker_tools | refactoring
   - Add ignore rule: mcp_tools_py.inspect_library -> mcp_tools_py.server (TYPE_CHECKING import)

Run all three code quality checks after changes.
Commit: "chore: add inspect_library to architecture boundary configs"
```

## WHERE

| File | Action |
|------|--------|
| `tach.toml` | MODIFY |
| `.importlinter` | MODIFY |

## WHAT — `tach.toml` Changes

Add new module entry:

```toml
[[modules]]
path = "mcp_tools_py.inspect_library"
layer = "tool_implementation"
depends_on = [
    { path = "mcp_tools_py.log_utils" }
]
```

Add to existing server module's `depends_on`:

```toml
# In the mcp_tools_py.server module, add:
{ path = "mcp_tools_py.inspect_library" }
```

## WHAT — `.importlinter` Changes

Update layers contract (line with `checker_tools | refactoring`):

```ini
mcp_tools_py.checker_tools | mcp_tools_py.refactoring | mcp_tools_py.inspect_library
```

Add ignore rule (alongside existing ones):

```ini
ignore_imports =
    mcp_tools_py.checker_tools -> mcp_tools_py.server
    mcp_tools_py.refactoring -> mcp_tools_py.server
    mcp_tools_py.inspect_library -> mcp_tools_py.server
```

## WHAT — `.importlinter` Forbidden-Imports Update

In the `[importlinter:contract:forbidden-imports]` section, add `mcp_tools_py.inspect_library` to the `forbidden_modules` list so that the new module is subject to the same import restrictions as other tool modules.

## DATA — No New Code

This step is config-only. No Python code changes.
