# Step 3: Update all skill files

> See [summary.md](summary.md) for full context on issue #173.

## Commit message

`chore: replace bash git with MCP tools in skills`

## WHERE

6 files, all under `.claude/skills/`:

1. `commit_push/SKILL.md`
2. `implementation_review/SKILL.md`
3. `implementation_review_supervisor/SKILL.md`
4. `plan_review/SKILL.md`
5. `rebase/SKILL.md`
6. `rebase/rebase_design.md`

## WHAT — per file

### 1. `commit_push/SKILL.md`

**allowed-tools changes:**
- Remove: `Bash(git status *)`, `Bash(git diff *)`, `Bash(git log *)`
- Add: `mcp__workspace__git_status`, `mcp__workspace__git_diff`, `mcp__workspace__git_log`

**Body changes:**
- Section "2. Review Changes": replace the bash code block (`git status` / `git diff`) with plain-text instruction to use `mcp__workspace__git_status` and `mcp__workspace__git_diff`

### 2. `implementation_review/SKILL.md`

**allowed-tools changes:**
- Remove: `Bash(git status *)`, `Bash(git diff *)`, `Bash(mcp-coder git-tool *)`
- Add: `mcp__workspace__git_status`, `mcp__workspace__git_diff`

**Body changes:**
- "First, ensure we're up to date" section: replace `git status` bash line with plain-text `mcp__workspace__git_status`
- "Code Review Request" section: replace `mcp-coder git-tool compact-diff` bash block with plain-text instruction to use `mcp__workspace__git_diff`

### 3. `implementation_review_supervisor/SKILL.md`

**allowed-tools changes:**
- Remove: `Bash(mcp-coder git-tool *)`
- Add: `mcp__workspace__git_diff`

**Body changes:** None — body doesn't reference `mcp-coder git-tool` directly (it delegates to subagents).

### 4. `plan_review/SKILL.md`

**allowed-tools changes:**
- Remove: `Bash(git status *)`
- Add: `mcp__workspace__git_status`

**Body changes:**
- "First, ensure we're up to date" section: replace `git status` bash line with plain-text `mcp__workspace__git_status`

### 5. `rebase/SKILL.md`

**allowed-tools changes:**
- Remove: `Bash(git status *)`, `Bash(git log *)`, `Bash(git diff *)`
- Add: `mcp__workspace__git_status`, `mcp__workspace__git_log`, `mcp__workspace__git_diff`

**Body changes:**
- Replace `git status` bash references with plain-text `mcp__workspace__git_status`
- Replace `git diff` bash references with plain-text `mcp__workspace__git_diff`
- Replace `git log` bash references with plain-text `mcp__workspace__git_log`
- The `!`git status`` hook at the top of the body should become `!`mcp__workspace__git_status``

### 6. `rebase/rebase_design.md`

**Body changes only** (no allowed-tools frontmatter):
- In the "Rebase-Specific Permissions" section, update the permissions list:
  - Remove `Bash(git status:*)`, `Bash(git log:*)` from the list
  - Add a note or separate section indicating these are now MCP tools: `mcp__workspace__git_status`, `mcp__workspace__git_log`
  - Note: `Bash(git diff:*)` stays in the rebase design doc list since rebase needs `git diff` during conflict resolution — but the *permission* was already replaced with MCP in the SKILL.md. Update the design doc to reflect MCP `mcp__workspace__git_diff` is used instead.

## HOW

Each file: edit YAML frontmatter `allowed-tools` list + edit markdown body. Same mechanical pattern across all files.

## KEY CONSTRAINT

When a bash code block references a replaced command, it must become a **plain-text instruction** (not a bash code block) for the MCP tool call. Example:

**Before:**
```markdown
## 2. Review Changes
\`\`\`bash
git status
git diff
\`\`\`
```

**After:**
```markdown
## 2. Review Changes
Use `mcp__workspace__git_status` to check working directory status, then `mcp__workspace__git_diff` to review changes.
```

## Verification

- Each file's `allowed-tools` has no Bash permissions for `git status`, `git diff`, `git log`, or `mcp-coder git-tool` (where applicable)
- Each file's `allowed-tools` has the corresponding MCP tools
- No bash code blocks remain that reference replaced commands
- Bash code blocks for non-replaced commands (`git fetch`, `git add`, `git commit`, `git push`, etc.) are unchanged

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_3.md.
Implement step 3: update all 6 skill files to replace Bash read-only git permissions with MCP tool equivalents in both allowed-tools frontmatter and body text. Replace bash code blocks for replaced commands with plain-text MCP tool instructions.
```
