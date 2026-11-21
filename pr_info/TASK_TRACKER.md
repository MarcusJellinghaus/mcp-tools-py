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

### Step 1: `--strict-markers` in pytest addopts, with regression test — [step_1.md](./steps/step_1.md)

- [x] Implementation: `tests/test_repo_pytest_config.py` (fails first), `pyproject.toml` addopts, `vulture_whitelist.py` comment, `.claude/CLAUDE.md` sentence
- [x] Quality checks (pytest targeted + full suite, pylint, mypy, ruff, format) — fix all issues
- [x] Commit message prepared

### Step 2: Fix the two marker comments in `toolkit.py` — [step_2.md](./steps/step_2.md)

- [ ] Implementation: update comments above `UNATTENDED_EXCLUDED_MARKERS` and `_STRICT_MARKERS_OFF` (comments only)
- [ ] Quality checks (pytest unit, pylint, mypy, ruff, format) — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review the full branch diff against the base branch
- [ ] PR summary prepared
