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

### Step 1: Data Models + Dependency ([detail](./steps/step_1.md))
- [x] Implementation: add `bandit>=1.7.5` to pyproject.toml, create `code_checker_bandit/models.py` and `__init__.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `feat(bandit): add data models and dependency`

### Step 2: JSON Parser + Tests ([detail](./steps/step_2.md))
- [x] Implementation: create `parsers.py` with `parse_bandit_json_output`, create `test_parsers.py`, update `__init__.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `feat(bandit): add JSON parser with tests`

### Step 3: LLM-Optimized Reporting + Tests ([detail](./steps/step_3.md))
- [x] Implementation: create `reporting.py` with grouping/sorting/formatting, create `test_reporting.py`, update `__init__.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `feat(bandit): add LLM-optimized reporting with tests`

### Step 4: Subprocess Runner + Tests ([detail](./steps/step_4.md))
- [x] Implementation: create `runners.py` with `run_bandit_check_impl`, create `test_runners.py`, update `__init__.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `feat(bandit): add subprocess runner with tests`

### Step 5: Server + Checker Tools Integration ([detail](./steps/step_5.md))
- [x] Implementation: add bandit binary detection in `server.py`, add `_register_bandit()` in `checker_tools.py`, create `test_integration.py`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit: `feat(bandit): register run_bandit_check MCP tool`

### Step 6: Architecture Boundary Configuration ([detail](./steps/step_6.md))
- [ ] Implementation: update `tach.toml` and `.importlinter` with `code_checker_bandit` module boundaries
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit: `chore(bandit): add architecture boundary config`

## Pull Request
- [ ] PR review: verify all steps complete and checks passing
- [ ] PR summary prepared
