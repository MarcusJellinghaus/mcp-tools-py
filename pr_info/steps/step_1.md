# Step 1: Update settings.local.json

> See [summary.md](summary.md) for full context on issue #173.

## Commit message

`chore: replace bash git permissions with MCP tools in settings`

## WHERE

- `.claude/settings.local.json`

## WHAT

In `permissions.allow` array:

**Remove:**
- `Bash(git diff:*)`
- `Bash(git log:*)`
- `Bash(git status:*)`
- `Bash(mcp-coder git-tool:*)`

**Add:**
- `mcp__workspace__git_log`
- `mcp__workspace__git_diff`
- `mcp__workspace__git_status`
- `mcp__workspace__git_merge_base`

**Keep unchanged:**
- `Bash(git fetch:*)`
- `Bash(git mv:*)`
- `Bash(git ls-tree:*)`

## HOW

Direct JSON edits — remove 4 entries, add 4 entries in the `allow` array.

## Verification

- File is valid JSON after editing
- All 4 removed entries are gone
- All 4 new entries are present
- Remaining Bash git entries (`fetch`, `mv`, `ls-tree`) are untouched

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_1.md.
Implement step 1: update .claude/settings.local.json to replace Bash read-only git permissions with MCP tool equivalents. Remove the 4 specified Bash permissions and add the 4 MCP tool permissions. Verify the JSON is valid after editing.
```
