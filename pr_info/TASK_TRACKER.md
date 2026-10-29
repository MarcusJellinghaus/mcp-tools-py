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

### Step 1: Collect count excludes deselected tests — [step_1.md](./steps/step_1.md)

- [x] Implementation: tests and `get_test_summary` header change
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Per-call `timeout_seconds` on the `move_symbol` tool — [step_2.md](./steps/step_2.md)

- [x] Implementation: plumbing test and `timeout_seconds` parameter
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 3: Parent-side snapshot cleanup for dry runs — [step_3.md](./steps/step_3.md)

- [x] Implementation: tests, `_missing_paths`, `_remove_new_paths`, child-side dry-run cleanup removed
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 4: Real-run failure reporting and cleanup — [step_4.md](./steps/step_4.md)

- [x] Implementation: tests, `_split_moved`, `_MOVE_SUCCESS_PREFIX`, `_cleanup_created_files` removed
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 5: Dry run shows rope's unified diff per symbol — [step_5.md](./steps/step_5.md)

- [ ] Implementation: test and per-symbol diffs in dry-run output
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 6: String-reference report (not rewritten) — [step_6.md](./steps/step_6.md)

- [ ] Implementation: tests, `_module_dotted`, `_string_ref_lines`, tool docstring update
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review the full branch diff against `main` and address findings
- [ ] PR summary prepared
