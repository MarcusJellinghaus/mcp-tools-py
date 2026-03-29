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

### Step 1: Add new functions (additive, non-breaking) + tests
> Details: [step_1.md](./steps/step_1.md)

- [ ] Implementation: add `threading` import, `__all__`, re-exported exceptions, move `check_tool_missing_error`/`truncate_stderr` above dataclasses, add `env_remove` field to `CommandOptions`, add `get_utf8_env()`, `prepare_env()`, `_run_heartbeat()`, `launch_process()` to `subprocess_runner.py`; add test classes `TestPrepareEnv`, `TestCommandOptionsEnvRemove`, `TestMergedUtilities`, `TestLaunchProcess`, `TestHeartbeat` to `test_subprocess_runner.py`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 2: Refactor existing functions to use new code + test cleanup
> Details: [step_2.md](./steps/step_2.md)

- [ ] Implementation: wire `prepare_env()` into `_run_subprocess()`, remove `_safe_preexec_fn()`, remove `structlog` dependency, replace with stdlib `logging`, narrow exception handling in `execute_subprocess()`, add heartbeat params to `execute_subprocess()`, add `encoding="utf-8"` + `errors="replace"` to `Popen` calls, add `check=False` to taskkill calls, narrow taskkill handler to `OSError`, update `utils/__init__.py` exports; update `test_execute_command_unexpected_error`, add `TestRunSubprocessUsesPrepareEnv` + `TestPrepareEnvIntegration`, drop low-value test classes and fixtures
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: verify `subprocess_runner.py` matches upstream (allowed diffs: import paths, hardcoded `CLAUDECODE` removal)
- [ ] PR summary prepared
