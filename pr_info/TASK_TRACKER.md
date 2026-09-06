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

- [x] [Step 1](./steps/step_1.md) — `PythonEnvironment` value object
- [x] [Step 2](./steps/step_2.md) — Probe script and `EnvironmentInfo`
- [x] [Step 3](./steps/step_3.md) — `get_library_source` runs in a child process
- [ ] [Step 4](./steps/step_4.md) — jedi `environment_path` + venv integration test
- [ ] [Step 5](./steps/step_5.md) — Move `FastMCPProtocol` out of `server.py`
- [ ] [Step 6](./steps/step_6.md) — `ToolContext`; `CheckerTools` + `FormatterTools`
- [ ] [Step 7](./steps/step_7.md) — Remaining three registrars; document the invariant

## Pull Request
