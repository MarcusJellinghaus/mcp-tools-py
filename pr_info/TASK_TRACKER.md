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

### Step 1: `from-global` import style preference
> [Detail](./steps/step_1.md) — Set `prefer_module_from_imports` in `_with_rope_project()` + test

- [x] Implementation: set rope preference + add test for from-import style
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `feat(refactoring): set from-global import style in rope project`

### Step 2: Batch `move_symbol` — signature change, loop, and validation
> [Detail](./steps/step_2.md) — `symbol_name` → `symbol_names` across all layers, batch loop, all-or-nothing validation

- [x] Implementation: signature change across rope_tools, rope_cli, __init__.py + batch loop with reverse-order iteration + upfront validation (duplicates, existence, collisions) + update all existing tests + add new batch tests
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit: `feat(move_symbol): batch move with signature change and validation`

### Step 3: Self-referencing import removal
> [Detail](./steps/step_3.md) — Post-move cleanup of self-referencing imports in destination

- [ ] Implementation: add `_remove_self_imports()` helper + integrate in `_move_symbol_impl()` + add test
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit: `feat(move_symbol): remove self-referencing imports after move`

### Step 4: Result output with review reminders
> [Detail](./steps/step_4.md) — Structured result output with notes

- [ ] Implementation: enhance `_move_symbol_impl()` result string + dry-run output + add test
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit: `feat(move_symbol): structured result output with review reminders`

### Step 5: Manual test plan update
> [Detail](./steps/step_5.md) — Update TEST_PLAN.md for new signature + batch test cases

- [ ] Implementation: update Tests 7a–7c to `symbol_names` + add Tests 7d–7f for batch moves + update PROGRESS_TRACKER.md
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit: `docs(test-plan): update move_symbol tests for batch signature`

## Pull Request

- [ ] PR review: verify all steps integrated correctly, no regressions
- [ ] PR summary prepared
