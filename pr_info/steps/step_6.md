# Step 6: Architecture Boundary Configuration

> **Context**: Read `pr_info/steps/summary.md` first for full architecture overview.

## Prompt

```
Implement Step 6 of Issue #149 (bandit security linter).
Read pr_info/steps/summary.md for architecture context, then read this step file.

Add the code_checker_bandit module to the architecture boundary configuration
in tach.toml and .importlinter. Follow the exact pattern used by code_checker_ruff.

After implementation, run all three code quality checks (pylint, pytest, mypy)
using MCP tools with the recommended fast unit test exclusions.
Also run: tools/tach_check.sh or tools/tach_check.bat
Also run: tools/lint_imports.sh or tools/lint_imports.bat
Commit: "chore(bandit): add architecture boundary config"
```

## WHERE

- **Modify**: `tach.toml`
- **Modify**: `.importlinter`

## WHAT

### `tach.toml`

Add new module block (after `code_checker_ruff`):

```toml
[[modules]]
path = "mcp_tools_py.code_checker_bandit"
layer = "tool_implementation"
depends_on = [
    { path = "mcp_tools_py.utils" },
    { path = "mcp_tools_py.log_utils" }
]
```

Add `code_checker_bandit` to `checker_tools` depends_on:

```toml
# In the checker_tools module block, add:
    { path = "mcp_tools_py.code_checker_bandit" },
```

### `.importlinter`

Add `mcp_tools_py.code_checker_bandit` to the layers contract (same layer as other checkers):

```ini
# In [importlinter:contract:layers], update the checker layer line:
    mcp_tools_py.code_checker_pytest | mcp_tools_py.code_checker_pylint | mcp_tools_py.code_checker_mypy | mcp_tools_py.code_checker_ruff | mcp_tools_py.code_checker_bandit
```

Also update the `[importlinter:contract:forbidden-imports]` section's `forbidden_modules` list to include `mcp_tools_py.code_checker_bandit`:

```ini
# In [importlinter:contract:forbidden-imports], add to forbidden_modules:
    mcp_tools_py.code_checker_bandit
```

## DATA

No code changes — configuration only.

## Notes

- `code_checker_vulture` is NOT in the `.importlinter` layers contract checker line (it's a simpler module that doesn't need layering). But `code_checker_bandit` follows the rich checker pattern (ruff/pylint/mypy) and should be included.
- The `tach.toml` entry mirrors `code_checker_ruff` exactly — same layer, same dependencies.
- The `checker_tools` module needs `code_checker_bandit` in its `depends_on` so tach allows the import.
