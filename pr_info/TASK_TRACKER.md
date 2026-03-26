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

### Step 1: Core Logic + Unit Tests (Mocked)
- [x] Implementation: create `inspect_library.py` with `_get_library_source()` + `InspectTools` class, and `tests/test_inspect_library.py` with mocked unit tests
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `feat: add get_library_source core logic with mocked unit tests`

### Step 2: Real-Import Tests + MCP Registration in `server.py`
- [x] Implementation: add real-import tests to `tests/test_inspect_library.py` and wire `InspectTools` into `server.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `feat: wire get_library_source into MCP server with real-import tests`

### Step 3: Architecture Config Updates
- [x] Implementation: update `tach.toml` and `.importlinter` to include `inspect_library` module boundaries
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit: `chore: add inspect_library to architecture boundary configs`

## Pull Request
- [ ] PR review: verify all steps complete, tests pass, no regressions
- [ ] PR summary prepared
