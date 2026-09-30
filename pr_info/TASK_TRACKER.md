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

### Step 1: Remove `-s` in `sanitize_extra_args` and record `show_output`
See [step_1.md](./steps/step_1.md)

- [x] Implementation: tests in `test_extra_args.py`, then `SanitizedArgs.show_output` and `sanitize_extra_args` changes
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Show captured output of passing tests
See [step_2.md](./steps/step_2.md)

- [x] Implementation: tests (reporting, checker_tools, server_params, integration), then `create_prompt_for_passing_output`, `show_output` wiring and docstrings
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

## Pull Request

- [ ] PR review: review the full branch diff against `main`
- [ ] PR summary prepared
