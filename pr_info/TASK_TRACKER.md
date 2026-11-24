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

### Step 1: Shared short-group splitter — [step_1.md](./steps/step_1.md)
- [x] Implementation: `split_short_group` used by `_values_taken`, `sanitize_extra_args`, `_option_spans` (tests in `test_short_groups.py`, update `test_extra_args.py`)
- [x] Quality checks (pylint, mypy, pytest) — fix all issues
- [x] Commit message prepared

### Step 2: Report flags in `effective_config` — [step_2.md](./steps/step_2.md)
- [x] Implementation: `OptionValue.label`, `EffectiveConfig.options`, new `_VALUE_OPTIONS`/`_FLAG_OPTIONS` entries, `_label` (tests in `test_effective_config.py`)
- [x] Quality checks (pylint, mypy, pytest) — fix all issues
- [x] Commit message prepared

### Step 3: `report_data.py` basics — [step_3.md](./steps/step_3.md)
- [x] Implementation: `strip_xdist_header`, `relative_path`, `format_log_record`; `Warning.lineno: int | None` (tests in `test_report_data.py`)
- [x] Quality checks (pylint, mypy, pytest) — fix all issues
- [x] Commit message prepared

### Step 4: Skips — entries, folding, module-level count — [step_4.md](./steps/step_4.md)
- [ ] Implementation: `SkipKey`, `folded_skips`, `skip_lines`, `module_skip_count`, `skipped_count`; `get_test_summary` uses `skipped_count` (tests in `test_report_data.py`)
- [ ] Quality checks (pylint, mypy, pytest) — fix all issues
- [ ] Commit message prepared

### Step 5: Warning groups and duration entries — [step_5.md](./steps/step_5.md)
- [ ] Implementation: `WarningGroup`, `warning_groups`, `warning_line`, `Duration`, `durations`, `stage_seconds` (tests in `test_report_data.py`)
- [ ] Quality checks (pylint, mypy, pytest) — fix all issues
- [ ] Commit message prepared

### Step 6: Failure blocks — one stage loop; passing output gains logs — [step_6.md](./steps/step_6.md)
- [ ] Implementation: `ALL_CAPTURE`, `capture_kinds`, public `Sections.named`, two-pass `_render_test` (teardown, header strip, logs, capture), passing-output logs, `SHOW_OUTPUT_NOTE` wording (tests in `test_failure_blocks.py`, update `test_failure_budget.py`)
- [ ] Quality checks (pylint, mypy, pytest) — fix all issues
- [ ] Commit message prepared

### Step 7: `report_extras.py` — flags, sections, empty-result lines — [step_7.md](./steps/step_7.md)
- [ ] Implementation: `ReportFlags`, `resolve_report_chars`, `report_flags`, `report_sections`, `_head_rows` (tests in `test_report_extras.py`)
- [ ] Quality checks (pylint, mypy, pytest) — fix all issues
- [ ] Commit message prepared

### Step 8: Hint line and flag notes — [step_8.md](./steps/step_8.md)
- [ ] Implementation: `hint_line`, `flag_notes`, `SNAPSHOT_NOTE`, `DURATIONS_MIN_NOTE` (tests in `test_report_extras.py`)
- [ ] Quality checks (pylint, mypy, pytest) — fix all issues
- [ ] Commit message prepared

### Step 9: Exit 5 — report plumbing and skip block — [step_9.md](./steps/step_9.md)
- [ ] Implementation: `_read_report`, report attached on exit 5, `skip_report` key, `skipped_block`, ERROR-branch append; remove unreachable branch (tests in `test_runners.py`, `test_checker_tools_formatting.py`, `test_report_extras.py`)
- [ ] Quality checks (pylint, mypy, pytest) — fix all issues
- [ ] Commit message prepared

### Step 10: `⚠️ Warnings: N` count — [step_10.md](./steps/step_10.md)
- [ ] Implementation: `warnings_part`, `format_error_text(show_warnings=...)`, count in `_format_pytest_result_with_details` (tests in `test_verdict.py`, `test_checker_tools_formatting.py`, new `test_toolkit_warnings_count.py`)
- [ ] Quality checks (pylint, mypy, pytest) — fix all issues
- [ ] Commit message prepared

### Step 11: `--show-capture` and `-s` output on every verdict with tests — [step_11.md](./steps/step_11.md)
- [ ] Implementation: `capture` parameter, `_with_passing_output` for PASSED/FAILED/ERROR (tests in `test_checker_tools_formatting.py`)
- [ ] Quality checks (pylint, mypy, pytest) — fix all issues
- [ ] Commit message prepared

### Step 12: Wire notes and tail block into `run_pytest_check` — [step_12.md](./steps/step_12.md)
- [ ] Implementation: `report_tail`, `has_tests`, flag notes and tail wired into `run_pytest_check` (reply-level tests beside `test_config_notes_reply.py`)
- [ ] Quality checks (pylint, mypy, pytest) — fix all issues
- [ ] Commit message prepared

### Step 13: End-to-end integration tests — [step_13.md](./steps/step_13.md)
- [ ] Implementation: `test_integration_report_flags.py` (4 cases); fix defects revealed in steps 1–12
- [ ] Quality checks (pylint, mypy, pytest incl. `integration` marker for this file) — fix all issues
- [ ] Commit message prepared

### Step 14: Docstring, README and architecture docs — [step_14.md](./steps/step_14.md)
- [ ] Implementation: `run_pytest_check` docstring, README `extra_args` row, `architecture.md`, `output-conventions.md`
- [ ] Quality checks (pylint, mypy, pytest, file size ≤ 750 lines) — fix all issues
- [ ] Commit message prepared

## Pull Request
- [ ] PR review: review full branch diff against base branch, address findings
- [ ] PR summary prepared (concise description, no attribution footer)
