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

### Step 1: Remove `--venv-path` from the MCP configs
See [step_1.md](./steps/step_1.md)

- [ ] Implementation: probe fails first, remove `--venv-path` from `.mcp.json` and `.mcp.macos.json`, probe passes, delete `.scratch/`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 2: Document the venv requirement
See [step_2.md](./steps/step_2.md)

- [ ] Implementation: edit `README.md`, `INSTALL.md` and `docs/architecture/architecture.md`, run the search and `git diff` checks
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review the full branch diff against the base branch
- [ ] PR summary prepared
