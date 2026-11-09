# Summary — Issue #67: Log checker internals at DEBUG; keep tool-layer start/completed at INFO

## Problem

Every checker run logs the same events twice at INFO: once in the tool layer
(`checker_tools/*_tool.py`) and again in the internal `code_checker_*` layers
(runners, parsers, reporting). For example, `run_mypy_check` writes five INFO
lines, and two of them repeat the same message.

## Design change

All checkers follow one logging rule:

| Layer | Modules | Routine log level |
|---|---|---|
| Tool layer | `checker_tools/*_tool.py` | **INFO** for start / completed (unchanged) |
| Internal layers | `code_checker_*/` (runners, parsers, reporting), `utils/ruff_parsing.py` | **DEBUG** (was INFO) |

- Only call sites change. Logger configuration, `log_utils`, function
  signatures and the interface between tool layer and runners all stay the same.
- `warning` / `error` calls keep their levels.
- The full subprocess command (from the mypy runner's start line) is now logged
  only at DEBUG. A mypy timeout still includes it in the error text.
- "Produced no output" lines (pylint, bandit, ruff) also go to DEBUG.
- INFO lines in the tool layer other than start/completed (pytest
  "extra_args sanitized"), plus those in `main.py`, `server.py` and
  `utils/environment_info.py`, are unchanged.
- `lint_imports_tool.py` gets no start/completed INFO lines. This exception is
  accepted.

## Files modified (all under `src/mcp_tools_py/`)

| File | Call sites (`logger.info` → `logger.debug`) |
|---|---|
| `code_checker_mypy/runners.py` | "Starting mypy check", "Mypy check completed" |
| `code_checker_mypy/parsers.py` | "Parsed mypy output" |
| `code_checker_pylint/runners.py` | "Starting pylint analysis", "Pylint subprocess completed", "Pylint analysis completed" |
| `code_checker_pylint/reporting.py` | "Starting pylint prompt generation", "No pylint issues found", "Pylint issues found, generating prompt" |
| `code_checker_pylint/parsers.py` | "Pylint produced no output" |
| `code_checker_pytest/runners.py` | "Starting pytest execution", "Pytest execution completed successfully", "Starting pytest code check", "Pytest code check completed" |
| `code_checker_bandit/parsers.py` | "Bandit produced no output" |
| `utils/ruff_parsing.py` | "Ruff produced no output" |

There are 15 call sites in 8 files. No files are created and no tests change.

## Tests

The issue decides against adding tests because this changes log levels only.
No existing test checks INFO level on an affected message:
- `tests/test_checker_tools.py` patches the tool-layer logger (`mypy_tool.logger`).
- `tests/test_code_checker/test_runners.py` checks only WARNING records.

The existing suite is the regression check.

## Steps

1. `step_1.md`: change the 15 internal `logger.info` calls to `logger.debug`, re-sweep, run checks, and make one commit.
