# Step 5: Add "Shared libraries" section to CLAUDE.md

**Summary:** [summary.md](./summary.md)

## Goal

Document the `mcp-coder-utils` dependency, the shim import pattern, and the "do not reimplement" rule so future contributors don't reintroduce direct imports or duplicate shared functionality.

## Test first

No automated test — this is documentation only.

## Implementation

### WHERE
`.claude/CLAUDE.md`

### WHAT
Add a new `## Shared libraries` section. Place it after the "About this repo" section and before "MCP Tools — mandatory".

### Content

```markdown
## Shared libraries

This project depends on `mcp-coder-utils` for subprocess execution, logging, and file I/O.

**Import rule:** never import `mcp_coder_utils` directly. Always use the local shim modules:

| Need | Import from |
|------|-------------|
| Logging (`log_function_call`, `setup_logging`, `OUTPUT`) | `mcp_tools_py.log_utils` |
| Subprocess (`execute_command`, `CommandResult`, etc.) | `mcp_tools_py.utils.subprocess_runner` |
| File I/O (`read_file`) | `mcp_tools_py.utils.file_utils` |

This is enforced by the `mcp_coder_utils_isolation` contract in `.importlinter`.

**Do not reimplement** functionality that exists in `mcp-coder-utils`. Check the `p_coder-utils` reference project before writing new utilities.
```

### ALGORITHM
```
1. Read .claude/CLAUDE.md
2. Insert the "Shared libraries" section after "About this repo" paragraph
3. Save file
```

## Verify

Run pylint, pytest, mypy — all must pass (documentation-only change, but confirm no regressions).

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_5.md.
Implement step 5: add the "Shared libraries" section to .claude/CLAUDE.md.
Place it after the "About this repo" section. Run all code quality checks after.
```
