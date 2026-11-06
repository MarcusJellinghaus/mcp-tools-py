# Summary: `run_tach_check` status line follows tach's exit code (#268)

## Problem

`run_tach_check` starts its reply with `tach check completed:` for every outcome, because `code_checker_tach/runners.py` never reads `return_code`. A failed architecture check has the same status line as a clean one. `_run_tach` in `toolkit_checks.py` reads the exit code for its `status`, but holds its own copy of the same text, so its finding message and `fix_text` have the same problem, including `tach check passed (no output).` on exit 1.

## Expected behaviour

The status line depends only on the exit code:

| Exit code | Output | Text |
|---|---|---|
| 0 | Yes | `tach check passed:\n{output}` |
| 0 | No | `tach check passed (no output).` |
| Non-zero | Yes | `tach check failed:\n{output}` |
| Non-zero | No | `tach check failed (exit code N, no output).` |

The timeout and execution-error branches stay as they are. Exit 0 with warnings says passed on purpose, with the warnings in the body. A clean run keeps its `[]` body.

## Architectural / design changes

- **One new shared function:** `format_tach_result(result: CommandResult) -> str` in `code_checker_tach/runners.py` becomes the only place that builds this text.
- **Both callers use it:** `run_tach_check` and `_run_tach`. The copied block in `_run_tach` is removed.
- **One new import edge:** `toolkit_checks` imports from `code_checker_tach.runners`, as it already does for the other `code_checker_*.runners` modules. No new layers, contracts or modules.
- **`_run_tach` keeps its own `execute_command`:** it needs the return code and the runner returns only text. Only the formatting is shared. Its tests also patch `mcp_tools_py.toolkit_checks.execute_command`.
- **Public contract change:** the reply text of `run_tach_check` changes from `completed` to `passed`/`failed`. No known parser reads it.

## Out of scope

- `_run_tach` reporting a config failure as `status="findings"` with the summary `tach found architecture boundary violations.`.
- `_run_tach` dropping warnings on exit 0 and reporting `tach found no issues.`.
- The log line at `checker_tools/tach_tool.py:43`, which means the process finished.
- `tests/test_checker_tools.py:625-629`, which mocks the runner and asserts its own mock value.

## Files to modify

No files or folders are created by the implementation, apart from these plan files.

| File | Change | Step |
|---|---|---|
| `src/mcp_tools_py/code_checker_tach/runners.py` | Add `format_tach_result`, call it from `run_tach_check`, update docstring | 1 |
| `src/mcp_tools_py/checker_tools/tach_tool.py` | Update tool docstring | 1 |
| `tests/test_code_checker_tach/test_runners.py` | Replace four tests with one parametrized test | 1 |
| `src/mcp_tools_py/toolkit_checks.py` | Remove copied block, call `format_tach_result`, update docstring | 2 |
| `tests/test_toolkit_check.py` | Parametrize the tach violation test and assert the message | 2 |

## Steps

1. [Shared formatter used by `run_tach_check`](./step_1.md)
2. [`_run_tach` uses the shared formatter](./step_2.md)
