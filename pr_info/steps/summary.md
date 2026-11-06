# Issue #53: mypy failures and blocking errors can be hidden or reported as success

## Goal

`run_mypy_check` and the toolkit `check` action must never report a failed mypy run as success, must not lose stderr, and must make an early stop visible. Both entry points report the same signals.

The issue is the source of the rationale and rejected options. Where a line number in the issue differs from the code, trust the code (the README `max_issues` row is now line 97, not 91).

## Architectural / design changes

| Area | Before | After |
|---|---|---|
| Failure detection | Only rc 2 with stderr and no messages was an error, labelled "Mypy configuration error" | One guard in the runner covers every failed exit, with the neutral text `mypy exited with code {rc}: {output}` |
| stderr | Available only inside the mixed `raw_output` | New `MypyResult.stderr` field. JSON lines are removed when stderr was the source of the parsed messages. `None` when `error` is set |
| Signals | None | `reporting.run_signals(result)` is the single source of the early-stop line and the warning. `create_mypy_prompt`, `get_mypy_prompt` and `_run_mypy` all use it |
| Success text | Literal in `CheckerTools._format_mypy_result` | `MYPY_SUCCESS_TEXT` constant in `reporting.py`, next to `MYPY_FAILURE_PREFIX` |
| rc 2 report | Blocker could be reduced to a count, or hidden by the location cap | The group holding the last error is always detailed without using a `max_issues` slot, and the last error is always listed. No fix-advice footer |
| Toolkit `_merge` | Always rebuilt `fix_text` from findings, discarding custom text | Uses each result's `fix_text`, falling back to a rebuild from that result's findings |
| Toolkit mypy mapping | Notes counted as findings, hints dropped, no signals | Notes excluded, hints in `fix_text`, signals in `summary`, full text in `raw` |

`Finding.message`, `Finding.key` and `ActionResult` do not change. `raw_output` keeps its content because `mcp_coder` reads it.

### Decisions settled during plan discussion

- **Single guard:** `failed = not messages if rc == 1 else rc != 0 and errors_found == 0`. This also catches negative exit codes (a process killed by a signal on POSIX). rc 1 with notes only stays a non-error, because `reveal_type` alone gives rc 1 in JSON mode.
- **Last error beyond the location cap:** appended after the first 5 locations, followed by `... and N more`. Otherwise a `misc` blocker after five other `misc` errors would stay hidden.
- **One-line collapse in `summary`:** `" ".join(text.split())`, with no truncation. The full text is in `raw`.
- **`raw` for mypy:** `result.error or result.stderr or ""`, so timeout text also appears in `raw`. Its `summary` is unchanged and keeps the retry advice.
- **Removed:** the rc 2 "Mypy returned configuration error" log block, along with the rest of that `if` block.

### Real mypy 2.4.1 behaviour, probed on Windows for this plan

| Fixture | Result |
|---|---|
| Plugin raising in `get_function_hook`, `reveal_type` in an earlier module | rc 2, one note on stdout, `INTERNAL ERROR` on stderr |
| Raising `typing_extensions.py` in the project root | rc 1, empty stdout, traceback on stderr |
| Found-twice layout from the issue | rc 2, one `error`, `code` null, line and column -1, multi-line `hint` |
| `python_version = "2.7"` | rc 2 with a usage error on stderr. Not an rc 0 warning, so do not use it for rc 0 tests |

## Files

### Modified: source

| File | Step | Change |
|---|---|---|
| `src/mcp_tools_py/code_checker_mypy/models.py` | 1 | `MypyResult.stderr` |
| `src/mcp_tools_py/code_checker_mypy/parsers.py` | 1 | `AttributeError` in the except, `strip_json_messages` |
| `src/mcp_tools_py/code_checker_mypy/runners.py` | 1 | `MYPY_EXIT_PREFIX`, single guard, stderr field, label removal |
| `src/mcp_tools_py/code_checker_mypy/reporting.py` | 2, 3, 5 | `MYPY_SUCCESS_TEXT`, `run_signals`, last-error group, footer, negative line, `format_hint_lines` |
| `src/mcp_tools_py/checker_tools/__init__.py` | 2 | Use `MYPY_SUCCESS_TEXT` |
| `src/mcp_tools_py/checker_tools/mypy_tool.py` | 2, 3 | `issues_found` log, `max_issues` docstring |
| `src/mcp_tools_py/toolkit_checks.py` | 4, 5 | `_merge`, `_run_mypy`, `_one_line` |

### Modified: docs

| File | Step | Change |
|---|---|---|
| `README.md` (line 97) | 3 | `max_issues` behaviour on rc 2 |
| `tests/mcp_tools_py_manual/TEST_PLAN.md` (lines 225, 232) | 3 | Expected output for 3e and 3f |

### Modified or created: tests

| File | Step |
|---|---|
| `tests/test_code_checker_mypy/test_parsers.py` | 1 |
| `tests/test_code_checker_mypy/test_runners.py` (including the comment at line 25) | 1 |
| `tests/test_code_checker_mypy/test_reporting.py` | 2, 3 |
| `tests/test_checker_tools.py` | 2 |
| `tests/test_toolkit.py` | 4 |
| `tests/test_toolkit_check_mypy.py` (**new**, because `test_toolkit_check.py` is already long) | 5 |
| `tests/test_code_checker_mypy/test_integration.py` | 6 |

No folders are created. `docs/architecture/architecture.md` needs no change.

## Steps

1. Runner: report every failed exit and expose stderr
2. Reporting: warning, early-stop line and success text
3. Reporting: rc 2 detail, footer, file-level errors and `max_issues` docs
4. Toolkit: `_merge` keeps each result's `fix_text`
5. Toolkit: mypy mapping (notes, hints, signals)
6. Real-mypy integration tests

## Checks for every step

Run these and fix everything they report before committing:

- `mcp__mcp-tools-py__run_pylint_check`
- `mcp__mcp-tools-py__run_pytest_check` with `extra_args=["-n", "auto", "-m", "not integration"]`
- `mcp__mcp-tools-py__run_mypy_check`
- `mcp__mcp-tools-py__run_format_code` immediately before committing

## Related

Companion issue MarcusJellinghaus/mcp_coder#1388 covers callers that ignore `MypyResult.error`. It is out of scope here. `rebase_checks.py:99` already honours `result.error` and will raise `CheckRunError` on the newly reported runs, which is correct.
