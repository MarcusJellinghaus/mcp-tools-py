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

### Step 1: Reword `fix.check`, add `fix.test` — [step_1.md](./steps/step_1.md)

- [x] Implementation: update `TestPromptFragments` tests, then reword `_FIX_CHECK_PROMPT`, add `_FIX_TEST_PROMPT` and the `fix.test` key in `prompt_fragments()`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: 600 s default timeout for check depths — [step_2.md](./steps/step_2.md)

- [x] Implementation: add `TestRunCheckTimeout` tests, then `_LONG_CHECK_TIMEOUT` / `_LONG_CHECK_TOOLS` in `_run_check` for mypy and pylint
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 3: Project environment from `VIRTUAL_ENV` — [step_3.md](./steps/step_3.md)

- [x] Implementation: autouse `VIRTUAL_ENV` fixture in `tests/conftest.py`, new `tests/test_toolkit_environment.py`, stale-env test in `tests/test_toolkit_verify.py`; then `_build_context`, `run`/`verify` guards, and the "Name Resolution" docs update
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 4: `test@quick` excludes registered `*integration` markers — [step_4.md](./steps/step_4.md)

- [x] Implementation: new `tests/test_toolkit_markers.py` (unit + real strict-marker run), then `_registered_markers` and the `quick` marker selection in `_run_test`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

## Pull Request

- [x] PR review: review the full branch diff against `main` and address findings
- [ ] PR summary prepared
