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

### Step 1: `read_pytest_config` and the `PYTEST*` test-env scrub — [step_1.md](./steps/step_1.md)

- [x] Implementation: tests (`test_pytest_config.py`, scrub fixture test, adapted `test_startup_time.py`) + `pytest_config.py` (`PytestConfig`, `read_pytest_config`, `_parse_bool`), `_clear_pytest_env` in `tests/conftest.py`, `_XDIST_WORKER_COUNT` in `tests/test_startup_time.py`
- [x] Quality checks (format, pylint, pytest, mypy, vulture, lint-imports) — fix all issues
- [x] Commit message prepared

### Step 2: `effective_config` and `addopts_notes` — [step_2.md](./steps/step_2.md)

- [x] Implementation: tests (`test_effective_config.py`) + `OptionValue`, `EffectiveConfig`, `effective_config`, `addopts_notes` and private helpers in `pytest_config.py`
- [x] Quality checks (format, pylint, pytest, mypy, vulture, lint-imports) — fix all issues
- [x] Commit message prepared

### Step 3: Coverage selection on `EffectiveConfig`; delete `get_pytest_addopts` — [step_3.md](./steps/step_3.md)

- [x] Implementation: updated tests (`test_coverage.py`, `test_coverage_selection_identity.py`, `test_project_config.py`, toolkit tests if needed) + `selection_line` / `selection_identity` on `EffectiveConfig`, wiring in `pytest_tool.py` and `toolkit.py`, delete `_effective_option`, `_option_value`, `get_pytest_addopts`
- [x] Quality checks (format, pylint, pytest, mypy, vulture, lint-imports) — fix all issues
- [x] Commit message prepared

### Step 4: `runners.py` — transport the exit code and pytest's `-m` error line — [step_4.md](./steps/step_4.md)

- [x] Implementation: tests (`test_runners.py`) + `_EXIT_CODE_ATTR`, `_MARKER_ERROR_ATTR`, `MARKER_ERRORS`, `marker_error_line`, `exit_code` / `marker_error` keys in `check_code_with_pytest`
- [x] Quality checks (format, pylint, pytest, mypy, vulture, lint-imports) — fix all issues
- [x] Commit message prepared

### Step 5: `marker_hint.py` — expression scan and marker notes — [step_5.md](./steps/step_5.md)

- [x] Implementation: tests (`test_marker_hint.py`) + `marker_hint.py` (`scan_expression`, `unknown_marker_names`, `marker_notes`, constants)
- [x] Quality checks (format, pylint, pytest, mypy, vulture, lint-imports) — fix all issues
- [x] Commit message prepared

### Step 6: Wire the notes into `run_pytest_check` — [step_6.md](./steps/step_6.md)

- [ ] Implementation: tests (`test_config_notes_reply.py`, `test_integration_marker_hint.py`) + `call_replaced_addopts_m` in `pytest_config.py`, `_defaults_may_explain` / `_defaults_select` and note wiring in `pytest_tool.py`
- [ ] Quality checks (format, pylint, pytest incl. the new integration test file, mypy, vulture, lint-imports) — fix all issues
- [ ] Commit message prepared

### Step 7: Docstring, README, architecture doc — [step_7.md](./steps/step_7.md)

- [ ] Implementation: docstring test in `test_config_notes_reply.py` + `run_pytest_check` docstring, README parameter rows, `docs/architecture/architecture.md`
- [ ] Quality checks (format, pylint, pytest, mypy, vulture, lint-imports) — fix all issues
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review the full branch diff against the issue #294 Acceptance list
- [ ] PR summary prepared
