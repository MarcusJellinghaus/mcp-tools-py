# Step 2: Update CLAUDE.md

> See [summary.md](summary.md) for full context on issue #173.

## Commit message

`docs: add MCP git tools to CLAUDE.md tool mapping`

## WHERE

- `.claude/CLAUDE.md`

## WHAT

### Tool mapping table (around line 11)

Add 4 new rows:

| Task | MCP tool |
|------|----------|
| Git log | `mcp__workspace__git_log` |
| Git diff | `mcp__workspace__git_diff` |
| Git status | `mcp__workspace__git_status` |
| Git merge-base | `mcp__workspace__git_merge_base` |

### Git operations section (around line 64)

Replace the current section that lists `git status / diff / commit / log / fetch / ls-tree` as Bash-allowed with two groups:

1. **MCP tools** (use these for read-only git): `mcp__workspace__git_status`, `mcp__workspace__git_diff`, `mcp__workspace__git_log`, `mcp__workspace__git_merge_base`
2. **Bash-only** (no MCP equivalent): `git commit`, `git fetch`, `git show`, `git ls-tree`

Note: `git show` is explicitly added to Bash-only list (previously unlisted).

Remove `git status / diff / log` from the Bash command list.

## HOW

Direct markdown edits in two sections of the file.

## Verification

- Tool mapping table includes 4 new git rows
- Git operations section clearly separates MCP tools from Bash-only commands
- `git show` is listed in Bash-only
- `git status`, `git diff`, `git log` are NOT in the Bash-only list

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_2.md.
Implement step 2: update .claude/CLAUDE.md to add MCP git tools to the tool mapping table and restructure the git operations section into MCP tools vs Bash-only commands.
```
