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

- [ ] [Step 1](./steps/step_1.md) — Update file_utils shim + swap pytest/utils.py consumer
- [ ] [Step 2](./steps/step_2.md) — Redirect all direct log_utils imports through shim
- [ ] [Step 3](./steps/step_3.md) — Redirect all direct subprocess_runner imports through shim
- [ ] [Step 4](./steps/step_4.md) — Add import-linter isolation contract
- [ ] [Step 5](./steps/step_5.md) — Add "Shared libraries" section to CLAUDE.md

## Pull Request
