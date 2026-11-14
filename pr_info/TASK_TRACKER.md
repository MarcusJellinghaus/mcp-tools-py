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

### Step 1: Run every probe in a fresh temporary working directory
See [step_1.md](./steps/step_1.md)

- [ ] Implementation: `side_effect_package` fixture and tests first (see them fail), then `run_probe` in `environment_info.py`, route all four probe callers through it, update architecture doc and README
- [ ] Quality checks: pylint, pytest (`-n auto`), mypy, lint-imports — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review the full branch diff against the summary and step plan
- [ ] PR summary prepared
