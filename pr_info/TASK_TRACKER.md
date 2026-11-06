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

### Step 1: Adopt the new `describe` and `verify` signatures

See [step_1.md](./steps/step_1.md).

- [x] Implementation (tests + production code): update `TestDescribe` in `tests/test_toolkit.py`, then the signatures in `src/mcp_tools_py/toolkit.py`
- [x] Quality checks: pylint, pytest, mypy, ruff — fix all issues
- [x] Commit message prepared

## Pull Request

- [ ] PR review: review the full branch diff against the base branch and address findings
- [ ] PR summary prepared
