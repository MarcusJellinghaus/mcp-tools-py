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

### Step 1: Scaffolding + Dependencies ([step_1.md](./steps/step_1.md))
**Commit:** `feat: add dependencies and scaffold refactoring module (#108)`

#### Part A: Refactoring module skeleton
- [x] Implementation — create `refactoring/__init__.py` with `RefactoringTools` class, `jedi_tools.py` placeholder, `rope_tools.py` placeholder, `tests/test_refactoring/__init__.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

#### Part B: Architecture & config updates
- [x] Implementation — add rope/jedi to `pyproject.toml` dependencies, register `integration` marker, rename layer in `tach.toml` and `.importlinter`, add `.ropeproject/` to `.gitignore`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

---

### Step 2: Extract CheckerTools from server.py ([step_2.md](./steps/step_2.md))
**Commit:** `refactor: extract CheckerTools from server.py (#108)`

#### Part A: Tests for CheckerTools extraction
- [x] Implementation — create `tests/test_checker_tools.py` with registration and formatting tests
- [x] Quality checks: pylint, pytest, mypy — fix all issues (import errors expected until Part B creates checker_tools.py)
- [x] Commit message prepared

#### Part B: Extract CheckerTools class
- [x] Implementation — create `src/mcp_tools_py/checker_tools.py` with `CheckerTools` class, move tool registrations and formatting methods from `server.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

#### Part C: Wire into server.py and update architecture config
- [x] Implementation — replace `_register_tools()` with `CheckerTools(self).register(self.mcp)`, update `tach.toml` server dependencies, verify `.importlinter`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

---

### Step 3: Jedi Tools — list_symbols + find_references ([step_3.md](./steps/step_3.md))
**Commit:** `feat: add list_symbols and find_references tools (#108)`

#### Part A: Tests for jedi tools
- [x] Implementation — create `tests/test_refactoring/test_jedi_tools.py` with list_symbols and find_references tests
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

#### Part B: Implement jedi_tools.py
- [x] Implementation — implement `list_symbols` and `find_references` in `src/mcp_tools_py/refactoring/jedi_tools.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

#### Part C: Register in RefactoringTools
- [ ] Implementation — register `list_symbols` and `find_references` as MCP tools in `refactoring/__init__.py`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

---

### Step 4: Rope Tools — move_symbol, rename, move_module ([step_4.md](./steps/step_4.md))
**Commit:** `feat: add move_symbol, rename, and move_module tools (#108)`

#### Part A: Tests for rope tools
- [ ] Implementation — create `tests/test_refactoring/test_rope_tools.py` with move_symbol, rename_symbol, and move_module tests
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

#### Part B: Implement rope_tools.py
- [ ] Implementation — implement `move_symbol`, `rename_symbol`, `move_module`, and helpers in `src/mcp_tools_py/refactoring/rope_tools.py`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

#### Part C: Register in RefactoringTools
- [ ] Implementation — register `move_symbol`, `rename`, and `move_module` as MCP tools in `refactoring/__init__.py`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

---

### Step 5: Integration Tests ([step_5.md](./steps/step_5.md))
**Commit:** `test: add end-to-end refactoring integration tests (#108)`

#### Part A: RefactoringTools registration tests
- [ ] Implementation — create `tests/test_refactoring/test_refactoring_tools.py` with registration and relative-path tests
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

#### Part B: End-to-end workflow tests
- [ ] Implementation — create `tests/test_refactoring/test_integration.py` with full workflow tests (split file, rename, move module)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

---

## Pull Request

- [ ] PR review — verify all steps complete, all checks green, architecture checks pass
- [ ] PR summary prepared with description of changes
