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

### Step 1: Migrate .mcp.json reference-project args to new KV format
- [x] Implementation: migrate 4 `--reference-project` values to `name=X,path=Y,url=Z` format and rename `p_coder_utils` → `p_coder-utils`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Add obsidian-wiki and search_reference_files permissions
- [x] Implementation: add 11 `mcp__obsidian-wiki__*` permissions and `mcp__workspace__search_reference_files` permission to `.claude/settings.local.json`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

## Pull Request
- [x] PR review completed
- [ ] PR summary prepared
