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

### Step 1: `run` returns `error` for an undeclared action or depth
See [step_1.md](./steps/step_1.md)

- [x] Implementation: tests (`test_unknown_action_is_error`, `test_undeclared_depth_is_error`) + validate against `describe().actions` before `_build_context` in `PythonToolkit.run`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 2: `verify` honours `action`
See [step_2.md](./steps/step_2.md)

- [x] Implementation: per-action verify tests (12 items incl. deptry, format/check/test, undeclared) + `_tool_item` and action-aware `verify`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 3: mypy errors-only findings, `raw` = mypy's raw output
See [step_3.md](./steps/step_3.md)

- [x] Implementation: rework `TestStatusSummaryRaw` / timeout tests, add `test_warning_severity_is_not_a_finding` + filter `severity == "error"` and `raw=result.raw_output or ""` in `_run_mypy`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 4: Locations in `fix_text`
See [step_4.md](./steps/step_4.md)

- [x] Implementation: location tests for helpers, check tools, mypy and test + optional `location`/`locations` args in `_finding_line`/`_result_from_findings`, line locations in pylint/ruff/bandit/deptry/mypy runners, node ids in `_run_test`
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 5: `test@unattended`
See [step_5.md](./steps/step_5.md)

- [x] Implementation: describe/permissions/prompt-fragment/run tests + `UNATTENDED_EXCLUDED_MARKERS`, `_STRICT_MARKERS_OFF`, `unattended` depth in `describe`/`_run_test`, `check_instructions.unattended` fragment
- [x] Quality checks: pylint, pytest, mypy — fix all issues
- [x] Commit message prepared

### Step 6: Depth-based pytest timeouts
See [step_6.md](./steps/step_6.md)

- [ ] Implementation: `TestRunTestTimeout` tests + `_LONG_TEST_TIMEOUT` applied via `replace(context, check_timeout=...)` for non-quick depths in `_run_test`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues (also run `test_malformed_timeout_leaves_no_temp_dir` explicitly)
- [ ] Commit message prepared

### Step 7: Failed collectors become findings
See [step_7.md](./steps/step_7.md)

- [ ] Implementation: collector/xdist/exit-code tests and flipped verdict tests + `_XDIST_KEY`, `_collector_findings`, `_is_collection_error`, collector findings before the `known` gate in `_run_test`
- [ ] Quality checks: pylint, pytest, mypy — fix all issues (also run `tests/test_toolkit_saved_coverage.py` explicitly)
- [ ] Commit message prepared

## Pull Request

- [ ] PR review: review the full branch diff against the summary and steps
- [ ] PR summary prepared
