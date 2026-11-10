# Summary — Bounded, relevant tool output (#60)

## Goal

Every text that reaches an LLM — MCP tool responses and `PythonToolkit`'s
`ActionResult.fix_text` — is **bounded**, **relevant first**, **honest** (cuts
are counted and named) and **navigable** (every cut ends with a drill-in hint
naming a real parameter, a sibling tool call, or a concrete narrowing action).

Truncation happens only at the presentation layer. Runners, parsers, models
and toolkit `Finding` keys keep the full data (mcp-coder's rebase baseline
compares key sets).

## Architectural / design changes

1. **One truncation primitive.** New `utils/report_budget.py` holds every shared
   limit and one function, `bound_text()`. It caps each line's length, keeps
   head and tail, replaces the middle with `[... N lines / M chars omitted ...]`,
   closes a code fence left open at the cut, and ends with an optional hint.
   It replaces pytest's `OutputBuilder`, verdict's caps, lint-imports' cap and
   `formatter/common.truncate_output`.
2. **Global guard.** `guard_output()` = `bound_text()` at the guard limits.
   `GuardedMCP` (in `utils/mcp_protocols.py`) wraps `FastMCP.tool()` so every
   registered tool's string return passes through the guard. It sits outermost,
   above `@log_function_call`, so logs keep the full output. `ToolServer` hands
   `GuardedMCP` to the six registrars; registrar code is unchanged.
3. **Shared renderers** in `report_budget.py`:
   - `render_locations(items, hint)`: `Location` items grouped by
     (file, message) into rows such as `- f.py: 57, 63, 73 (+12) — <message>`,
     at most `LOCATIONS_PER_RULE` rows. Overflow ends with a count line that
     includes the hint.
   - `render_summary(rows, title, top, hint)`: top `SUMMARY_TOP` rule rows,
     then `... and N more rules (M occurrences), largest: S101 3444, ...` and
     the hint. `top=None` means uncapped (`max_issues=0`).
4. **Per-tool budgets sit below the guard.** `TOOL_LINES`/`TOOL_CHARS` (300 /
   16k) are used by pytest, lint-imports and toolkit `fix_text`. The guard
   (`GUARD_LINES`/`GUARD_CHARS`, 400 / 24k) is a safety net only.
5. **Structured vulture and tach.** Each gets `parsers.py` (a NamedTuple model
   plus a parser) and `reporting.py`. Runners return a result tuple instead of
   strings, which removes the vulture string sentinels and the duplicated tach
   command in `toolkit_checks`. Both tools gain `max_issues`. Toolkit keys
   become precise: `vulture|<file>|<kind>|<name-or-message>` and
   `tach|<file>|<usage_module>|<dependency>`. tach warnings go into `summary`
   only. Unparseable output passes through raw, bounded by the guard.
6. **pytest failure rendering.** Each test gets its own share of the budget,
   in this order: message → longrepr (tail-kept) → stderr → stdout (tail-kept).
   The traceback is dropped when a longrepr is present. A reserved list names
   every failed test that got no detail. Drill-in hint:
   `extra_args=['<nodeid>', '-vv']`. With `coverage=True` the digest is built
   first and the failure section gets the remaining budget.
7. **Toolkit `fix_text`.** `_result_from_findings` renders findings grouped by
   rule with `render_locations` and bounds the text at `TOOL_LINES`. `_merge`
   splits the budget evenly across the results that have a `fix_text`. vulture
   and tach now go through `_result_from_findings`; mypy's and lint-imports'
   direct setters are bounded by `_merge`, which every check depth goes through.

## Decisions taken for this plan

- Limits: guard 400 lines / 24 000 chars; per-line cap 500 chars; per-tool
  300 lines / 16 000 chars; 10 location rows per rule with 10 line numbers per
  row; summary top 20; `MAX_FAILURES` 10; failed-ID list 50.
- mypy `max_issues: int = 3` (no longer `None`).
- vulture and tach `max_issues: int = 1`, matching pylint, ruff and bandit.
- Formatters drop `truncate_output` and rely on the guard (issue step 8). The
  toolkit format action's `raw` stays unbounded on purpose: no LLM reads it.
- Refactoring tools rely on the guard only. Its fixed hint ("narrow the
  request") is the concrete narrowing action.

## Files

### Created
- `src/mcp_tools_py/utils/report_budget.py`
- `src/mcp_tools_py/code_checker_vulture/parsers.py`
- `src/mcp_tools_py/code_checker_vulture/reporting.py`
- `src/mcp_tools_py/code_checker_tach/parsers.py`
- `src/mcp_tools_py/code_checker_tach/reporting.py`
- `docs/architecture/output-conventions.md`
- Tests: `tests/test_report_budget.py`, `tests/test_output_guard.py`,
  `tests/test_code_checker_pylint/test_reporting_budget.py`,
  `tests/test_code_checker_ruff/test_reporting_budget.py`,
  `tests/test_code_checker_bandit/test_reporting_budget.py`,
  `tests/test_code_checker_deptry/test_reporting_budget.py`,
  `tests/test_code_checker_mypy/test_reporting_budget.py`,
  `tests/test_code_checker_pytest/test_failure_budget.py`,
  `tests/test_code_checker_pytest/test_output_budget.py`,
  `tests/test_code_checker_lint_imports/test_output_budget.py`,
  `tests/test_code_checker_vulture/test_parsers.py`,
  `tests/test_code_checker_vulture/test_reporting.py`,
  `tests/test_code_checker_tach/test_parsers.py`,
  `tests/test_code_checker_tach/test_reporting.py`,
  `tests/test_code_checker_ruff/test_fix_report_budget.py`,
  `tests/test_toolkit_fix_text_budget.py`, `tests/test_toolkit_check_vulture.py`,
  `tests/test_toolkit_check_tach.py`

### Modified
- `src/mcp_tools_py/utils/mcp_protocols.py` (`GuardedMCP`)
- `src/mcp_tools_py/server.py`
- `src/mcp_tools_py/formatter/common.py`, `black_runner.py`, `isort_runner.py`, `ruff_runner.py`
- `src/mcp_tools_py/code_checker_pylint/reporting.py`
- `src/mcp_tools_py/code_checker_ruff/reporting.py`
- `src/mcp_tools_py/code_checker_bandit/reporting.py`
- `src/mcp_tools_py/code_checker_deptry/reporting.py`
- `src/mcp_tools_py/code_checker_mypy/reporting.py`, `checker_tools/mypy_tool.py`
- `src/mcp_tools_py/code_checker_pytest/reporting.py`, `verdict.py`
- `src/mcp_tools_py/checker_tools/__init__.py`, `checker_tools/pytest_tool.py`
- `src/mcp_tools_py/code_checker_lint_imports/runners.py`
- `src/mcp_tools_py/code_checker_vulture/runners.py`, `__init__.py`, `checker_tools/vulture_tool.py`
- `src/mcp_tools_py/code_checker_tach/runners.py`, `__init__.py`, `checker_tools/tach_tool.py`
- `src/mcp_tools_py/toolkit_checks.py`
- `docs/architecture/architecture.md`
- Existing tests that assert exact output text (expect broad churn).

## Steps

1. Shared limits, `bound_text`, global guard
2. Formatters drop `truncate_output`
3. Shared renderers + pylint
4. ruff check
5. bandit + deptry
6. mypy
7. pytest failure rendering
8. pytest passing output, verdict caps, coverage budget, `OutputBuilder` removal
9. lint-imports cap
10. vulture structured output
11. tach structured output
12. ruff fix report
13. Toolkit `fix_text`
14. Documentation

## Every step

- TDD: write the tests first, then the implementation.
- Each touched tool gets one budget test: a large synthetic result stays within
  budget and ends with the drill-in hint.
- Before committing: `run_pylint_check`, `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`,
  `run_mypy_check`, then `run_format_code`. All must pass. One commit per step.
- Keep every file under 750 lines. Put new tests in new files.
