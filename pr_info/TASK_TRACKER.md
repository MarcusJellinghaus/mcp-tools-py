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

### Step 1: Add `_is_tool_available()` and shrink `_check_tool_availability()`
- [x] Implementation: production code (`server.py`) + tests (`test_tool_availability.py`)
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Migrate `checker_tools.py` and `formatter_tools.py` consumers to `_is_tool_available()`
- [ ] Implementation: production code (`checker_tools.py`, `formatter_tools.py`) + tests (`test_checker_tools.py`, `test_formatter_tools.py`)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 3: Update `test_server_params.py` patches
- [ ] Implementation: test updates (`test_server_params.py`)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request
- [ ] PR review completed
- [ ] PR summary prepared
