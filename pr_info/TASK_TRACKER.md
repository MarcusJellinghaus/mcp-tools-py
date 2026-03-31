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

### Step 1: Add `resolve_target_directories()` helper + tests
> [Detail](./steps/step_1.md) — `src/mcp_tools_py/utils/project_config.py`, `tests/test_project_config.py`

- [x] Implementation: tests (`TestResolveTargetDirectories`) + production code in `utils/project_config.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `refactor: add shared resolve_target_directories helper`

### Step 2: Create `code_checker_vulture/` runner module + tests
> [Detail](./steps/step_2.md) — new `src/mcp_tools_py/code_checker_vulture/` package, `tach.toml`

- [x] Implementation: tests (`tests/test_code_checker_vulture/test_runners.py`) + `runners.py` + `__init__.py` + `tach.toml` update
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `refactor: extract vulture runner into code_checker_vulture module`

### Step 3: Wire up all 3 tools in `checker_tools.py` + update runners + update tests
> [Detail](./steps/step_3.md) — `checker_tools.py`, pylint/mypy runners & reporting, `formatter_tools.py`, `test_checker_tools.py`

- [x] Implementation: update `checker_tools.py` to use `resolve_target_directories` + `run_vulture_check`; remove fallback logic from pylint/mypy runners; update reporting signatures; refactor `formatter_tools.py`; update tests
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `refactor: use pyproject.toml auto-detection in checker tools`

## Pull Request

- [ ] PR review: verify all steps integrated correctly, no regressions
- [ ] PR summary prepared
