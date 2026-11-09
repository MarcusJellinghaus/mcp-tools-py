# Step 1 — Lower internal checker INFO logs to DEBUG

## LLM prompt

> Read `pr_info/steps/summary.md`, then carry out `pr_info/steps/step_1.md`.
> In the 8 files listed below, change exactly the 15 listed `logger.info(`
> calls to `logger.debug(`. Leave the arguments and `extra` unchanged, and do
> not touch any other code. Run the re-sweep and the checks below. All of them
> must pass. Make one commit.

## WHERE

Under `src/mcp_tools_py/`:

| File | Messages to change |
|---|---|
| `code_checker_mypy/runners.py` | "Starting mypy check", "Mypy check completed" |
| `code_checker_mypy/parsers.py` | "Parsed mypy output" |
| `code_checker_pylint/runners.py` | "Starting pylint analysis", "Pylint subprocess completed", "Pylint analysis completed" |
| `code_checker_pylint/reporting.py` | "Starting pylint prompt generation", "No pylint issues found", "Pylint issues found, generating prompt" |
| `code_checker_pylint/parsers.py` | "Pylint produced no output" |
| `code_checker_pytest/runners.py` | "Starting pytest execution", "Pytest execution completed successfully", "Starting pytest code check", "Pytest code check completed" |
| `code_checker_bandit/parsers.py` | "Bandit produced no output" |
| `utils/ruff_parsing.py` | "Ruff produced no output" |

Do not change:
- `logger.warning` / `logger.error` calls
- `checker_tools/*`
- `main.py`, `server.py`, `utils/environment_info.py`
- the docstring example in `code_checker_pytest/models.py`

## WHAT

No new functions and no signature changes. Each listed call changes only its
method name:

```python
logger.info("Starting mypy check", extra={...})   # before
logger.debug("Starting mypy check", extra={...})  # after
```

## HOW

No changes to imports, decorators or logger configuration. Every module keeps
its existing module-level `logger`.

## ALGORITHM

```
for each (file, message) in WHERE table:
    find the logger.info( call whose first argument is message
    if not found: write one line to pr_info/.blocked.txt and stop
    replace "logger.info(" with "logger.debug(" on that call
search "logger\.info\(" in src/mcp_tools_py/code_checker_*/ and utils/ruff_parsing.py
    → only allowed hit: docstring in code_checker_pytest/models.py
```

## DATA

No changes to return values or data structures. Only the log record level
changes, from INFO (20) to DEBUG (10).

## Tests (TDD)

None to add. The issue decides against them because this changes log levels
only, and no existing test checks INFO on these messages (see summary). The
existing suite must still pass.

## Checks

- `mcp__mcp-tools-py__run_pylint_check`
- `mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`
- `mcp__mcp-tools-py__run_mypy_check`
- `mcp__mcp-tools-py__run_format_code` before committing

## Commit

`refactor(logging): log checker internals at DEBUG (#67)`
