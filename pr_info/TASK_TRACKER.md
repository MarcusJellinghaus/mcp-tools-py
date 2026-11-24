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

### Step 1: Shim `utils/user_app_data.py` + import contract + shim docs
See [step_1.md](./steps/step_1.md)

- [x] Implementation (tests + production code)
- [x] Quality checks (pylint, pytest, mypy, lint-imports) — fix all issues
- [x] Commit message prepared

### Step 2: `EffectiveConfig.n` — effective `-n` value and its source
See [step_2.md](./steps/step_2.md)

- [x] Implementation (tests + production code)
- [x] Quality checks (pylint, pytest, mypy) — fix all issues
- [x] Commit message prepared

### Step 3: `workers.py` config loader, verify data, test isolation fixtures
See [step_3.md](./steps/step_3.md)

- [x] Implementation (tests + production code)
- [x] Quality checks (pylint, pytest, mypy, lint-imports, tach) — fix all issues
- [x] Commit message prepared

### Step 4: Toolkit `verify()` item `pytest_workers`
See [step_4.md](./steps/step_4.md)

- [ ] Implementation (tests + production code)
- [ ] Quality checks (pylint, pytest, mypy) — fix all issues
- [ ] Commit message prepared

### Step 5: CPU sampler — platform seam, raw `GetSystemTimes`, exact math, median
See [step_5.md](./steps/step_5.md)

- [ ] Implementation (tests + production code)
- [ ] Quality checks (pylint, pytest, mypy) — fix all issues
- [ ] Commit message prepared

### Step 6: Resolver `resolve_workers` and the `workers:` line
See [step_6.md](./steps/step_6.md)

- [ ] Implementation (tests + production code)
- [ ] Quality checks (pylint, pytest, mypy) — fix all issues
- [ ] Commit message prepared

### Step 7: Wire sizing into `check_code_with_pytest` (+ integration tests)
See [step_7.md](./steps/step_7.md)

- [ ] Implementation (tests + production code)
- [ ] Quality checks (pylint, pytest incl. `test_integration_workers.py`, mypy) — fix all issues
- [ ] Commit message prepared

### Step 8: Wire the workers note into the MCP tool `run_pytest_check`
See [step_8.md](./steps/step_8.md)

- [ ] Implementation (tests + production code)
- [ ] Quality checks (pylint, pytest, mypy) — fix all issues
- [ ] Commit message prepared

### Step 9: Wire the workers note into the toolkit `_run_test`
See [step_9.md](./steps/step_9.md)

- [ ] Implementation (tests + production code)
- [ ] Quality checks (pylint, pytest, mypy, file size ≤ 750) — fix all issues
- [ ] Commit message prepared

### Step 10: User docs — `docs/user-config.md`, README, upgrade notes, architecture overview
See [step_10.md](./steps/step_10.md)

- [ ] Implementation (documentation)
- [ ] Quality checks (pylint, pytest, mypy) — fix all issues
- [ ] Commit message prepared

### Step 11: Agent guidance — remove the `-n auto` rule
See [step_11.md](./steps/step_11.md)

- [ ] Implementation (documentation)
- [ ] Quality checks (pylint, pytest, mypy) — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review all changes against issue #298 and `summary.md`
- [ ] PR summary prepared
