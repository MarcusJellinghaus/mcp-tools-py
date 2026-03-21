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

### Step 1: SanitizedArgs dataclass + sanitize_extra_args() with unit tests — [step_1.md](./steps/step_1.md)

- [x] Part A: Create unit tests for sanitize_extra_args() in `tests/test_code_checker_pytest/test_extra_args.py`
- [x] Part B: Add `SanitizedArgs` dataclass to `src/mcp_tools_py/code_checker_pytest/models.py`
- [x] Part C: Export `SanitizedArgs` from `src/mcp_tools_py/code_checker_pytest/__init__.py`
- [x] Part D: Implement `sanitize_extra_args()` in `src/mcp_tools_py/code_checker_pytest/utils.py`
- [x] Run quality checks (pylint, pytest, mypy) and fix all issues
- [x] Prepare git commit message for Step 1

### Step 2: Simplify server.py run_pytest_check + defensive error handling + test updates — [step_2.md](./steps/step_2.md)

- [x] Part A: Remove `verbosity` and `show_details` from `run_pytest_check` signature in `src/mcp_tools_py/server.py`
- [x] Part B: Add `sanitize_extra_args` import to `src/mcp_tools_py/server.py`
- [x] Part C: Integrate `sanitize_extra_args` and always show details in `run_pytest_check` body
- [x] Part D: Wrap entire `run_pytest_check` body in defensive try/except (return string, never raise)
- [x] Part E: Update `tests/test_server_params.py` — remove obsolete tests, update assertions, add new tests
- [x] Run quality checks (pylint, pytest, mypy) and fix all issues
- [x] Prepare git commit message for Step 2

### Step 3: Improve error propagation in runners.py — [step_3.md](./steps/step_3.md)

- [x] Part A: Include raw stderr/stdout in error messages for "no tests found" raise sites in `src/mcp_tools_py/code_checker_pytest/runners.py`
- [x] Run quality checks (pylint, pytest, mypy) and fix all issues
- [x] Prepare git commit message for Step 3

### Step 4: Integration test file rename and cleanup — [step_4.md](./steps/step_4.md)

- [ ] Part A: Rename `test_integration_show_details.py` to `test_integration_formatting.py`, rename class, remove obsolete toggle tests
- [ ] Run quality checks (pylint, pytest, mypy) and fix all issues
- [ ] Prepare git commit message for Step 4

---

## Pull Request

- [ ] Run full test suite and all quality checks (pylint, pytest, mypy) across entire codebase
- [ ] Review all changes for consistency with summary.md and Decisions.md
- [ ] Prepare PR title and summary description
