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

<!-- Tasks populated from pr_info/steps/ by prepare_task_tracker -->

### Step 1: probe.py — stdlib info field + scope subcommand

- [x] Implementation (tests + production code) — see [step_1.md](./steps/step_1.md)
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: environment_info.py — EnvironmentInfo.stdlib + resolve_scope()

- [x] Implementation (tests + production code) — see [step_2.md](./steps/step_2.md)
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 3: library_search.py — directory search core

- [x] Implementation (tests + production code) — see [step_3.md](./steps/step_3.md)
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 4: library_search.py — LibrarySearchTools registrar

- [x] Implementation (tests + production code) — see [step_4.md](./steps/step_4.md)
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 5: wire into server, architecture configs, and docs

- [x] Implementation (production code + updated tests/docs) — see [step_5.md](./steps/step_5.md)
- [x] Quality checks: tach, lint-imports, pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

## Pull Request

- [ ] PR review (diff matches [summary.md](./steps/summary.md); no unrelated changes)
- [ ] PR description written/updated
