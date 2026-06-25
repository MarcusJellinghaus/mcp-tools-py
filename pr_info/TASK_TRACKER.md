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

### Step 1: Bandit temp-file JSON capture + empty-file guard
See [step_1.md](./steps/step_1.md)

- [ ] Implementation: rework `tests/test_code_checker_bandit/test_runners.py` to the file seam (assert `-o <file>` in argv, `execute_command` mock `side_effect` writes the report, add empty/missing-file guard test), then update `src/mcp_tools_py/code_checker_bandit/runners.py` (`output_path` arg + `-o <file>` in `_build_bandit_command`; temp-dir lifecycle, read file, anomaly guard, `finally` cleanup in `run_bandit_check_impl`)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 2: move_module / move_symbol AttributeError hint hardening
See [step_2.md](./steps/step_2.md)

- [ ] Implementation: add two tests to `tests/test_refactoring/test_rope_tools.py` (import `_move_module_impl`/`_move_symbol_impl`, patch `create_move` to raise `AttributeError`, assert original text + `Hint:` line + cleanup), then append the hint via `isinstance(exc, AttributeError)` in the existing broad handlers of `_move_module_impl` and `_move_symbol_impl` in `src/mcp_tools_py/refactoring/rope_tools.py`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] Address PR review feedback
- [ ] Final summary of changes
