# Step 9 — lint-imports cap moves to the shared budget

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_9.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- `src/mcp_tools_py/code_checker_lint_imports/runners.py` (`_format_report`)
- New test: `tests/test_code_checker_lint_imports/test_output_budget.py`; update the tests
  that import `MAX_OUTPUT_LINES` or assert `_TRUNCATION_MARKER` at line 301

## WHAT / HOW
- Delete `MAX_OUTPUT_LINES` and `_TRUNCATION_MARKER`. Add
  `_CONTRACT_HINT = "Run with --contract <name> for individual results."`
- `_format_report` ends with `return bound_text("\n".join(lines), hint=_CONTRACT_HINT)`.
  It keeps the head (info lines + state header), so "first non-empty line is the state
  header or an info line" still holds.

## ALGORITHM
None.

## DATA
Unchanged `str`.

## Tests (write first)
- A BROKEN report with 2000 body lines → ≤ `TOOL_LINES` lines; the first non-info line is
  `=== BROKEN: ...`; the output contains the omitted marker and ends with `_CONTRACT_HINT`.
- A short report is unchanged and has no hint.
