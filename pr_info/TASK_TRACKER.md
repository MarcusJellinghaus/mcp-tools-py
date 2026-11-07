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

### Step 1: Raise the `import-linter` floor and verify it — [step_1.md](./steps/step_1.md)

- [ ] Implementation: raise `import-linter` to `>=2.12` in `pyproject.toml` and verify via scratch probe (fresh venv with `import-linter==2.12`: install, `lint-imports` keeps 4 contracts, `tests/test_target_scripts_contract.py` 3 passed)
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review all changes against the summary and step
- [ ] PR summary prepared
