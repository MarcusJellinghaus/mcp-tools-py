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

### Step 1: Shared limits, `bound_text`, global guard
See [step_1.md](./steps/step_1.md)
- [x] Implementation (tests + production code)
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Formatters drop `truncate_output`
See [step_2.md](./steps/step_2.md)
- [x] Implementation (tests + production code)
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 3: Shared renderers + pylint
See [step_3.md](./steps/step_3.md)
- [x] Implementation (tests + production code)
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 4: ruff check
See [step_4.md](./steps/step_4.md)
- [ ] Implementation (tests + production code)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 5: bandit + deptry
See [step_5.md](./steps/step_5.md)
- [ ] Implementation (tests + production code)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 6: mypy
See [step_6.md](./steps/step_6.md)
- [ ] Implementation (tests + production code)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 7: pytest failure rendering
See [step_7.md](./steps/step_7.md)
- [ ] Implementation (tests + production code)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 8: pytest passing output, verdict caps, coverage budget, `OutputBuilder` removal
See [step_8.md](./steps/step_8.md)
- [ ] Implementation (tests + production code)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 9: lint-imports cap moves to the shared budget
See [step_9.md](./steps/step_9.md)
- [ ] Implementation (tests + production code)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 10: vulture structured output
See [step_10.md](./steps/step_10.md)
- [ ] Implementation (tests + production code)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 11: tach structured output
See [step_11.md](./steps/step_11.md)
- [ ] Implementation (tests + production code)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 12: ruff fix report
See [step_12.md](./steps/step_12.md)
- [ ] Implementation (tests + production code)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 13: Toolkit `fix_text`
See [step_13.md](./steps/step_13.md)
- [ ] Implementation (tests + production code)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 14: Documentation
See [step_14.md](./steps/step_14.md)
- [ ] Implementation (documentation updates)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request
- [ ] PR review: review full branch diff against `main`, address findings
- [ ] PR summary prepared
