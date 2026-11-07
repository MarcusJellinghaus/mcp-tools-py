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

### Step 1: Shared formatter used by `run_tach_check` — [step_1.md](./steps/step_1.md)

- [ ] Implementation: parametrized `run_tach_check` test in `tests/test_code_checker_tach/test_runners.py`, `format_tach_result` in `runners.py`, docstring updates in `runners.py` and `tach_tool.py`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 2: `_run_tach` uses the shared formatter — [step_2.md](./steps/step_2.md)

- [ ] Implementation: parametrize `test_tach_violation_is_degraded_finding` in `tests/test_toolkit_check.py`, `_run_tach` calls `format_tach_result` in `toolkit_checks.py`, docstring update
- [ ] Quality checks: pylint, pytest, mypy (plus lint-imports, tach) — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review all changes across steps
- [ ] PR summary prepared
