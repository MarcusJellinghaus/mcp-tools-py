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

### Step 1: Resolver `resolve_test_paths` in `project_config.py`
See [step_1.md](./steps/step_1.md)

- [x] Implementation: rebase onto `origin/main` + force-push, precondition guard, tests in `tests/test_resolve_test_paths.py`, add `resolve_test_paths`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Runner and replies accept `None`
See [step_2.md](./steps/step_2.md)

- [x] Implementation: tests + `None` support in `runners.py`, `coverage_store.py`, `pytest_tool.py`, `toolkit.py` (`_with_note`, `test_paths_note`)
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 3: Flip the defaults to `None`
See [step_3.md](./steps/step_3.md)

- [x] Implementation: integration tests, default flips in `main.py`/`server.py`/`tool_context.py`/`runners.py`, updated pins, docs
- [x] Quality checks: pylint, pytest (including integration), mypy — fix all issues
- [x] Commit message prepared

## Pull Request

- [ ] PR review: review all changes against `pr_info/steps/summary.md`
- [ ] PR summary prepared
