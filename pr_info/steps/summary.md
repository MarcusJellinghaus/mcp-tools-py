# Summary — #293: report slowest tests, skip reasons, warnings and logs through pytest's own flags

Issue #293 is the specification. Its decision numbers (D1–D26) are referenced throughout these steps; read the issue
(`github_issue_view(293)`) when a step says "per D<n>".

## Goal

The parsed JSON report already holds durations, skip reasons, warnings and log records; none reach the
`run_pytest_check` reply. pytest's own flags (`--durations`, `-r…`, `--show-capture`, `-s`, `--snapshot-update`)
select what is rendered from the report. Default output stays short: counts, at most one hint line, logs inside
failing-test blocks.

## Architectural / design changes

1. **One short-option splitter** (`code_checker_pytest/utils.py: split_short_group`). `_values_taken`,
   `_scan_args`, `sanitize_extra_args` and `pytest_config._option_spans` all use it. Combined groups (`-svrw`,
   `-vkrs`, `-pno:cacheprovider`, `-vWerror`) are read letter by letter; a value-taking letter ends the group.
   `sanitize_extra_args` drops its `xvsql`-only special case and strips `s`/`v` from any group.
2. **`effective_config` tracks the report flags** through its existing last-wins loop. A new
   `EffectiveConfig.options: dict[str, OptionValue]` holds every tracked option; `OptionValue` gains a `label`
   (the call spelling, e.g. `-r s`, `--report-chars=s`, `-rw`).
3. **New module `code_checker_pytest/report_data.py`** — pure extraction from `PytestReport`: xdist header strip,
   relative paths, log-record formatting, skip entries + pytest-exact folding, module-level skip count, warning
   groups, duration entries. No rendering of whole sections, no budget.
4. **New module `code_checker_pytest/report_extras.py`** — rendering of this issue's report-level output:
   `report_flags()` (flag resolution incl. pytest's `getreportopt`), the `-rs` / `-rw` / `--durations` sections,
   empty-result lines, the hint line, the flag notes, and the exit-5 skip block.
5. **Budget reuse.** `reporting._Sections` becomes public `Sections` and gains `named(label, text)`; the report-level
   sections use it, so the existing "Not shown, budget used up: …" notice names dropped report sections too.
   Priority: failure blocks → `-s` passing output → report sections + hint; coverage digest keeps its share.
6. **Failure blocks use one stage loop** over setup/call/teardown: teardown failures render (D26), the xdist
   `[gwN]` header is stripped, logs appear per stage (D23), and `--show-capture` selects stdout/stderr/log (D12).
   `include_print_output: bool` becomes `capture: frozenset[str]`.
7. **Fixed placement in the reply** (`run_pytest_check`): flag notes ("no effect", `--durations-min`, snapshot) join
   the existing top notes; sections, empty-result lines and the hint form one tail block after the main reply and
   before the coverage digest, hint last. Clean run = one line.
8. **Counts.** `get_test_summary` adds module-level skips to `⏭️ Skipped` (reaches the toolkit, D14/D16).
   `⚠️ Warnings: N` only in `run_pytest_check`: appended in `CheckerTools._format_pytest_result_with_details`
   (only `run_pytest_check` calls it) and via a new opt-in `format_error_text(..., show_warnings=False)` keyword.
9. **Exit 5** (D18): `runners.run_tests` parses the report before raising and attaches it to the exception
   (same pattern as `_COMMAND_ATTR`); `check_code_with_pytest` returns it under a new `skip_report` key. The
   unreachable `returncode == 5 and report_exists` branch is removed. Error text keeps "No Tests Found".

## Files

| Action | Path |
|---|---|
| Create | `src/mcp_tools_py/code_checker_pytest/report_data.py` |
| Create | `src/mcp_tools_py/code_checker_pytest/report_extras.py` |
| Modify | `src/mcp_tools_py/code_checker_pytest/utils.py` |
| Modify | `src/mcp_tools_py/code_checker_pytest/pytest_config.py` |
| Modify | `src/mcp_tools_py/code_checker_pytest/models.py` |
| Modify | `src/mcp_tools_py/code_checker_pytest/reporting.py` |
| Modify | `src/mcp_tools_py/code_checker_pytest/verdict.py` |
| Modify | `src/mcp_tools_py/code_checker_pytest/runners.py` |
| Modify | `src/mcp_tools_py/checker_tools/__init__.py` |
| Modify | `src/mcp_tools_py/checker_tools/pytest_tool.py` |
| Create | `tests/test_code_checker_pytest/test_short_groups.py` |
| Create | `tests/test_code_checker_pytest/test_report_data.py` |
| Create | `tests/test_code_checker_pytest/test_report_extras.py` |
| Create | `tests/test_code_checker_pytest/test_failure_blocks.py` |
| Create | `tests/test_code_checker_pytest/test_integration_report_flags.py` |
| Modify | `tests/test_code_checker_pytest/test_extra_args.py`, `test_effective_config.py`, `test_failure_budget.py`, `test_runners.py`, `test_verdict.py` |
| Modify | `tests/test_checker_tools_formatting.py`, `tests/test_toolkit_test.py` |
| Modify | `README.md`, `docs/architecture/architecture.md`, `docs/architecture/output-conventions.md` |

## Steps

1. Short-group splitter shared by `_scan_args`, `sanitize_extra_args`, `_option_spans`.
2. Report flags in `effective_config` (`options`, `label`).
3. `report_data.py` basics: header strip, relative path, log formatting; `Warning.lineno: int`.
4. Skips: entries, folding, module-level count; corrected `⏭️ Skipped` in `get_test_summary`.
5. Warning groups and duration entries in `report_data.py`.
6. Failure blocks: one stage loop (teardown, header, logs, `--show-capture`); passing output gains logs.
7. `report_extras.py`: `report_flags`, sections, empty-result lines (with `Sections.named`).
8. `report_extras.py`: hint line and flag notes.
9. Exit-5 plumbing and skip block.
10. `⚠️ Warnings: N` count.
11. `--show-capture` and `-s` passing output on every verdict with tests.
12. Wire notes and tail block into `run_pytest_check`.
13. End-to-end integration tests.
14. Docstring, README, architecture docs.

## Checks for every step

Run `mcp__mcp-tools-py__run_pylint_check`, `run_mypy_check`, and
`run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`; integration tests of the touched area with
`markers=["integration"]`. Run `run_format_code` before committing. One commit per step.
