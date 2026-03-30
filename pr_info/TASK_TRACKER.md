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

### Step 1: Remove dead structlog imports from reporting modules
- [x] Implementation: remove unused `import structlog` and `structured_logger` from `code_checker_pytest/reporting.py` and `code_checker_mypy/reporting.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Migrate main.py and server.py to stdlib-only logging
- [x] Implementation: remove structlog, rename `stdlogger` → `logger` in main.py, consolidate dual log calls using `extra={}`, fix f-string log calls in server.py
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 3: Migrate subprocess_runner.py to stdlib-only logging
- [x] Implementation: remove structlog, convert all 8 `structured_logger` calls to `logger` with `extra={}` dicts
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 4: Migrate checker_tools.py to stdlib-only logging
- [x] Implementation: remove structlog, merge 17 dual log calls across 5 checker methods, replace f-strings with lazy `%s` formatting
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 5: Migrate pylint modules to stdlib-only logging
- [x] Implementation: remove structlog from `code_checker_pylint/parsers.py` (5 calls), `runners.py` (5 calls), `reporting.py` (4 calls) — convert to `logger` with `extra={}`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 6: Migrate mypy and pytest runner modules to stdlib-only logging, update docs
- [ ] Implementation: remove structlog from `code_checker_mypy/parsers.py` (2 calls), `runners.py` (4 calls), `code_checker_pytest/runners.py` (7 calls) — convert to `logger` with `extra={}`, fix f-string log calls, update `docs/architecture/architecture.md` Section 8
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request
- [ ] PR review: verify no module except `log_utils.py` imports structlog, no f-string log calls remain
- [ ] PR summary prepared
