# Task Status Tracker

## Instructions for LLM

This tracks **Feature Implementation** consisting of multiple **Tasks**.

**Summary:** See [summary.md](./steps/summary.md) for implementation overview.

**How to update tasks:**
1. Change [ ] to [x] when implementation step is fully complete (code + checks pass)
2. Change [x] to [ ] if task needs to be reopened
3. Add brief notes in the linked detail files if needed
4. Keep it simple - just GitHub-style checkboxes

**Task format:**
- [x] = Task complete (code + all checks pass)
- [ ] = Task not complete
- Each task links to a detail file in steps/ folder

---

## Tasks

### Step 1: Update settings.local.json — replace bash git permissions with MCP tools
> [step_1.md](./steps/step_1.md)

- [ ] Implementation: remove 4 Bash git permissions, add 4 MCP tool permissions in `.claude/settings.local.json`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared: `chore: replace bash git permissions with MCP tools in settings`

### Step 2: Update CLAUDE.md — add MCP git tools to tool mapping and git operations section
> [step_2.md](./steps/step_2.md)

- [ ] Implementation: add 4 MCP git tool rows to tool mapping table, restructure git operations section into MCP vs Bash-only
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared: `docs: add MCP git tools to CLAUDE.md tool mapping`

### Step 3: Update all 6 skill files — replace bash git with MCP tools
> [step_3.md](./steps/step_3.md)

- [ ] Implementation: update allowed-tools and body text in `commit_push/SKILL.md`, `implementation_review/SKILL.md`, `implementation_review_supervisor/SKILL.md`, `plan_review/SKILL.md`, `rebase/SKILL.md`, `rebase/rebase_design.md`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared: `chore: replace bash git with MCP tools in skills`

## Pull Request

- [ ] PR review: verify all steps completed and checks pass
- [ ] PR summary prepared
