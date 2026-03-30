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

### Step 1: Shared utility `utils/project_config.py` + tests
- [x] Implementation: `TargetDirs` dataclass, `get_target_directories()` function, tests in `tests/test_project_config.py`, export from `utils/__init__.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Formatter runners (`black_runner.py` + `isort_runner.py`) + tests
- [x] Implementation: `formatter/__init__.py`, `black_runner.py` with `run_black()`, `isort_runner.py` with `run_isort()`, tests in `tests/test_black_runner.py` and `tests/test_isort_runner.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 3: `FormatterTools` class + MCP tool registration + tests
- [ ] Implementation: `formatter/formatter_tools.py` with `FormatterTools` class, update `formatter/__init__.py` re-export, tests in `tests/test_formatter_tools.py`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 4: Server rename + wiring (all integration changes)
- [ ] Implementation: rename `CodeCheckerServer` → `ToolServer`, wire `FormatterTools`, add black/isort availability, move deps to main, update `tach.toml`, `.importlinter`, and all affected tests
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request
- [ ] PR review: verify all steps integrated correctly
- [ ] PR summary prepared
