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

### Step 1: Harden `_with_rope_project()` — disable cache + gitignore filtering
> Disable rope's persistent cache (`ropefolder=None`) and add gitignore-aware file filtering via `igittigitt` to reduce rope's scan scope.

- [x] Implementation: add `igittigitt` dependency, `_build_ignored_resources()`, `read_gitignore_rules()`, `apply_gitignore_filter()`, update `_with_rope_project()`, and write tests ([step_1.md](./steps/step_1.md))
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: ~~Multiprocessing timeout wrapper~~ (superseded by Step 3)
> Originally added `multiprocessing.Process` timeout wrapper. Failed in MCP server context due to Windows pipe inheritance.

- [x] Implementation ([step_2.md](./steps/step_2.md))
- [x] Superseded by Step 3

### Step 3: Replace multiprocessing with subprocess isolation
> Run rope operations in isolated subprocesses via `rope_cli.py`, using the same `execute_command` pattern as pytest/pylint/mypy runners. Fixes the MCP hang.

- [x] Implementation: add `rope_cli.py`, `_run_rope_subprocess()`, revert to sync tools with `@log_function_call` ([step_3.md](./steps/step_3.md))
- [x] Quality checks: pylint, pytest, mypy — all pass
- [x] Manual test plan: all 36 tests pass (see `pr_info/STATUS_REPORT_2026-03-25.md`)
- [x] Commit: `925712b fix(refactoring): run rope in subprocess to prevent MCP hang`

### Step 4: Cleanup
> Remove dead code and fragile tests.

- [x] Remove "real project dir" integration tests (fragile, depend on sample_project state; tmp_path tests already cover the same)
- [x] Remove unused `import rope.base.project` (duplicate of `from rope.base.project import Project`)
- [x] Remove unused `apply_gitignore_filter()` function (copied from p_workspace but never called)
- [ ] Quality checks: pylint, pytest, mypy (MCP tools-py server not available in session — run manually)

### Step 5: Robustness improvements
> Harden `rope_cli.py` error handling and subprocess result reporting.

- [ ] Add `try/except` in `rope_cli.main()` to catch unhandled exceptions and return structured JSON errors instead of raw tracebacks
- [ ] Add `try/except` around `json.dumps()` in `rope_cli.py` as safety net
- [ ] Include truncated stderr in `_run_rope_subprocess()` successful results for debugging (rope warnings/logs go to stderr)
- [ ] Quality checks: pylint, pytest, mypy

## Pull Request

- [ ] PR review: verify all steps integrated correctly
- [ ] PR summary prepared
