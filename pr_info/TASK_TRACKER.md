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

### Step 1: Read-only `addopts` accessor
See [step_1.md](./steps/step_1.md)

- [x] Implementation: tests + `_load_pyproject` and `get_pytest_addopts` in `utils/project_config.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: Source-only lookup for `coverage_source`
See [step_2.md](./steps/step_2.md)

- [x] Implementation: tests + `_read_source_dirs`, `_read_test_dirs`, `resolve_coverage_source` in `utils/project_config.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 3: `SanitizedArgs.path_args`
See [step_3.md](./steps/step_3.md)

- [x] Implementation: tests + `path_args` field in `models.py`, populated by `sanitize_extra_args`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 4: Coverage run plumbing
See [step_4.md](./steps/step_4.md)

- [x] Implementation: tests + new `code_checker_pytest/coverage.py` with `coverage_args`, `read_coverage_report`, `read_fail_under`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 5: Selection echo
See [step_5.md](./steps/step_5.md)

- [x] Implementation: tests + `selection_line` and `_option_value` in `coverage.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 6: Coverage digest formatter
See [step_6.md](./steps/step_6.md)

- [x] Implementation: tests + `format_coverage_digest` and `_ranges` in `coverage.py`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 7: Wire coverage into `run_pytest_check`
See [step_7.md](./steps/step_7.md)

- [x] Implementation: handler + integration tests, `pytest_tool.py` parameters, `pyproject.toml` dev dependency, README and architecture docs
- [x] Quality checks: pylint, pytest (incl. integration), mypy, lint-imports — fix all issues
- [x] Commit message prepared

## Pull Request

- [ ] PR review: review the full branch diff against `main`
- [ ] PR summary prepared
