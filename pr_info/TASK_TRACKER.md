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

### Step 1: Stop misreading extra_args values as paths — [step_1.md](./steps/step_1.md)

- [x] Implementation: tests first, then `_OPTION_VALUES`/`_values_taken`/`_positional_args` in `utils.py`, keep `tests` in `sanitize_extra_args`, add the default test folder before `extra_args` in `runners.py`, new integration test file
- [x] Quality checks: pylint, pytest (unit + new integration file), mypy — fix all issues
- [x] Commit message prepared: `fix(pytest): stop misreading extra_args values as paths (#49)`

### Step 2: Lead failure replies with counts and unrun tests — [step_2.md](./steps/step_2.md)

- [x] Implementation: tests first, then `selected_count`/`did_not_run_line` in `reporting.py`, counts first in the `FAILED` branch of `checker_tools/__init__.py`, README update
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared: `feat(pytest): lead failure replies with counts and unrun tests (#49)`

### Step 3: Report selected tests and IDs for --collect-only — [step_3.md](./steps/step_3.md)

- [ ] Implementation: tests first, then `SanitizedArgs.collect_only`, `_scan_args`, `collected_test_ids`, `format_collect_only_text`, `format_suspicious_text` deselected count, wiring in `checker_tools`/`pytest_tool.py`/`runners.py`/`toolkit.py`, README update
- [ ] Quality checks: pylint, pytest (unit + integration extra_args file), mypy — fix all issues
- [ ] Commit message prepared: `feat(pytest): report selected tests and IDs for --collect-only (#49)`

## Pull Request

- [ ] PR review: review the full branch diff against `main`, fix issues found
- [ ] PR summary prepared
