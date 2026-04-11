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

### Step 1: FormatterResult model + update both runners

Detail: [step_1.md](./steps/step_1.md)

- [x] Implementation: Create `formatter/models.py` with `FormatterResult` dataclass, update `black_runner.py` and `isort_runner.py` to return `FormatterResult` with `files_changed` parsing, update `formatter_tools.py` for compatibility, update all affected tests
- [x] Quality checks pass: pylint, pytest, mypy — fix all issues
- [x] Commit: `refactor(formatter): add FormatterResult model, update runners`

### Step 2: Extract `run_format_code` into `runner.py` + update MCP wrapper

Detail: [step_2.md](./steps/step_2.md)

- [ ] Implementation: Create `formatter/runner.py` with plain `run_format_code()` and tests, update `formatter_tools.py` to thin MCP wrapper delegating to `runner.py`, update `formatter/__init__.py` exports, update all affected tests
- [ ] Quality checks pass: pylint, pytest, mypy — fix all issues
- [ ] Commit: `refactor(formatter): extract run_format_code into runner.py`

### Step 3: Add `check_line_length_conflicts` + wire into MCP wrapper

Detail: [step_3.md](./steps/step_3.md)

- [ ] Implementation: Add `check_line_length_conflicts()` to `utils/project_config.py` with tests, wire into `formatter_tools.py` MCP wrapper, add wiring tests
- [ ] Quality checks pass: pylint, pytest, mypy — fix all issues
- [ ] Commit: `feat(formatter): add line-length conflict pre-check`

## Pull Request

- [ ] PR review: verify all steps integrated correctly
- [ ] PR summary prepared
