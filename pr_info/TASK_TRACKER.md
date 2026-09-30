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

### Step 1: Strict ruff parser
See [step_1.md](./steps/step_1.md)

- [x] Implementation: tests + strict `parse_ruff_json_output` with `_invalid_reason`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Ruff command overrides and flag pre-check
See [step_2.md](./steps/step_2.md)

- [ ] Implementation: tests (unit + integration) + `--no-fix`/`--no-fix-only` overrides, rejected flags, extra_args hint, tool docstrings
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 3: Strict pylint parser
See [step_3.md](./steps/step_3.md)

- [ ] Implementation: tests + strict `parse_pylint_json_output` with `_invalid_reason`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 4: Strict bandit parser and CWE line
See [step_4.md](./steps/step_4.md)

- [ ] Implementation: tests + strict `parse_bandit_json_output`, CWE line only when `cwe_id` is set
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review all changes against the summary and steps
- [ ] PR summary prepared
