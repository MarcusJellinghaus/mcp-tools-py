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

- [ ] Implementation: add `igittigitt` dependency, `_build_ignored_resources()`, `read_gitignore_rules()`, `apply_gitignore_filter()`, update `_with_rope_project()`, and write tests ([step_1.md](./steps/step_1.md))
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

### Step 2: Multiprocessing timeout wrapper + CLI plumbing
> Add `--refactoring-timeout` CLI arg, thread it through server to rope functions, and wrap each rope operation in a `multiprocessing.Process` for timeout protection.

- [ ] Implementation: add `_run_with_timeout()`, `_worker()`, split public functions into outer + `_*_impl`, add `timeout` param threading from CLI through server, and write tests ([step_2.md](./steps/step_2.md))
- [ ] Quality checks: pylint, pytest, mypy — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: verify all steps integrated correctly
- [ ] PR summary prepared
