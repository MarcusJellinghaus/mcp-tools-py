# Issue #173: Prefer MCP git tools over bash git commands in Claude config

## Problem

Read-only git operations (`git_log`, `git_diff`, `git_status`, `git_merge_base`) are now available as MCP tools (from mcp-workspace#77). These run without permission prompts, improving automated workflows. Config and documentation need updating to prefer them over Bash equivalents.

## Architectural / Design Changes

**Before:** All git operations used `Bash(git ...)` permissions. Read-only commands (`git status`, `git diff`, `git log`) required Bash permission grants in both global settings and per-skill `allowed-tools`.

**After:** Read-only git operations use dedicated MCP tools (`mcp__workspace__git_status`, `mcp__workspace__git_diff`, `mcp__workspace__git_log`, `mcp__workspace__git_merge_base`). Write operations (`git commit`, `git fetch`, `git push`, `git rebase`, etc.) remain Bash-only. The `mcp-coder git-tool` CLI usage (including `compact-diff`) is replaced by `mcp__workspace__git_diff`.

**Key design decisions:**
- Full replacement — no dual Bash+MCP permissions for the same operation
- Skill body text must match allowed-tools: bash code blocks for replaced commands become plain-text MCP tool references
- `git show` explicitly added to Bash-only list (no MCP equivalent, previously unlisted)

## Scope

No code changes. Config and documentation only.

## Files Modified

| File | Change |
|------|--------|
| `.claude/settings.local.json` | Remove 4 Bash permissions, add 4 MCP permissions |
| `.claude/CLAUDE.md` | Add MCP git tools to tool mapping, update git operations section |
| `.claude/skills/commit_push/SKILL.md` | Replace Bash read-only git → MCP in allowed-tools + body |
| `.claude/skills/implementation_review/SKILL.md` | Replace Bash git + mcp-coder git-tool → MCP in allowed-tools + body |
| `.claude/skills/implementation_review_supervisor/SKILL.md` | Replace mcp-coder git-tool → MCP in allowed-tools |
| `.claude/skills/plan_review/SKILL.md` | Replace Bash git status → MCP in allowed-tools + body |
| `.claude/skills/rebase/SKILL.md` | Replace Bash read-only git → MCP in allowed-tools + body |
| `.claude/skills/rebase/rebase_design.md` | Update permissions documentation |

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Update `settings.local.json` | `chore: replace bash git permissions with MCP tools in settings` |
| 2 | Update `CLAUDE.md` | `docs: add MCP git tools to CLAUDE.md tool mapping` |
| 3 | Update all 6 skill files | `chore: replace bash git with MCP tools in skills` |
