# Step 2 — Formatters drop `truncate_output`

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_2.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- `src/mcp_tools_py/formatter/common.py`: delete `MAX_LINES` and `truncate_output`
- `src/mcp_tools_py/formatter/black_runner.py`, `isort_runner.py`, `ruff_runner.py`:
  drop the import and pass the text through unchanged (5 call sites)
- `tests/test_formatter_common.py`: delete the two `truncate_output` tests

## WHAT / HOW
- `output=truncate_output(x)` becomes `output=x`.
- `run_format_code`'s MCP response is now bounded only by the step-1 guard. The toolkit
  format action's `raw` stays unbounded on purpose: no LLM reads it.

## ALGORITHM
None.

## DATA
`FormatterResult.output` holds the full text.

## Tests (write first)
- In an existing formatter tool test file (e.g. `tests/test_formatter_tools.py`), add one
  test: a formatter result with 1000 output lines, returned through a `GuardedMCP`-registered
  `run_format_code` (or through `guard_output` applied to the tool's text), stays
  ≤ `GUARD_LINES` lines and ends with `GUARD_HINT`.
- Add a runner test asserting that an output longer than 200 lines is no longer cut by
  the runner.
