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

### Step 1: `tool` parameter on `resolve_target_directories`, passed at every call site
See [step_1.md](./steps/step_1.md)

- [x] Implementation (tests + production code): `tests/test_target_directories_call_sites.py`, update pinned tests, add `TargetTool` and `tool` parameter, pass it at all 13 call sites
- [x] Quality checks (format, pylint, pytest, mypy) — fix all issues
- [x] Commit message prepared

### Step 2: `script-directories` in `resolve_target_directories`
See [step_2.md](./steps/step_2.md)

- [ ] Implementation (tests + production code): `tests/test_script_directories.py`, `_read_script_dirs`, new resolver body
- [ ] Quality checks (format, pylint, pytest, mypy) — fix all issues
- [ ] Commit message prepared

### Step 3: Docs and MCP tool docstrings
See [step_3.md](./steps/step_3.md)

- [ ] Implementation: `target_directories` docstrings of seven MCP tools, `docs/pyproject-configuration.md`, `docs/README.md`, `docs/architecture/architecture.md`, `README.md`
- [ ] Quality checks (format, pylint, pytest, mypy) — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review full branch diff against base branch
- [ ] PR summary prepared
