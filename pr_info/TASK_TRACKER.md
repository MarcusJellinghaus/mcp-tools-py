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

### Step 1: Models and Parsers — [step_1.md](./steps/step_1.md)
- [x] Implementation: `RuffMessage`/`RuffResult` models, `parse_ruff_json_output`, tests in `test_parsers.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Reporting — [step_2.md](./steps/step_2.md)
- [x] Implementation: `reporting.py` with grouping/sorting/formatting, tests in `test_reporting.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 3: Runners — [step_3.md](./steps/step_3.md)
- [x] Implementation: `runners.py` with `run_ruff_check_impl`/`run_ruff_fix_impl`, tests in `test_runners.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 4: Server Discovery + Checker Tools Registration — [step_4.md](./steps/step_4.md)
- [ ] Implementation: ruff binary discovery in `server.py`, register tools in `checker_tools.py`, update test fixtures
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 5: Architecture Config + Dependency — [step_5.md](./steps/step_5.md)
- [ ] Implementation: add `ruff>=0.9.0` to `pyproject.toml`, update `tach.toml` and `.importlinter`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request
- [ ] PR review: all steps completed and passing
- [ ] PR summary prepared
