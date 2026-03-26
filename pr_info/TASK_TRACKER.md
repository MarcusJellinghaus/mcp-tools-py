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

### Step 1: Add lint-imports availability check to `server.py` + tests
> Detail: [step_1.md](./steps/step_1.md)

- [x] Implementation: update `_check_tool_availability()` in `server.py` and tests in `test_tool_availability.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `feat: add lint-imports availability check via file existence`

### Step 2: Add `run_lint_imports_check` tool to `checker_tools.py` + tests
> Detail: [step_2.md](./steps/step_2.md)

- [x] Implementation: add `_register_lint_imports()` to `CheckerTools`, update registration count test, add tool handler tests
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit: `feat: add run_lint_imports_check MCP tool`

## Pull Request

- [ ] PR review: verify all steps integrated correctly
- [ ] PR summary prepared
