# Step 6: Migrate mypy and pytest runner modules to stdlib-only logging

> **Reference:** See `pr_info/steps/summary.md` for full context.

## Goal

Remove structlog from the remaining checker packages: mypy parsers (2 calls), mypy runners (4 calls), pytest runners (7 calls).

## WHERE

- `src/mcp_tools_py/code_checker_mypy/parsers.py`
- `src/mcp_tools_py/code_checker_mypy/runners.py`
- `src/mcp_tools_py/code_checker_pytest/runners.py`

## WHAT

No new functions. Transform existing log calls.

## HOW — mypy/parsers.py

Remove `import structlog` and `structured_logger = ...`.

Convert 2 calls:
```python
# structured_logger.debug("Non-JSON line in mypy output", line_num=..., content=...)
logger.debug("Non-JSON line in mypy output", extra={"line_num": line_num, "content": line[:100]})

# structured_logger.info("Parsed mypy output", total_messages=..., severities=...)
logger.info("Parsed mypy output", extra={"total_messages": len(messages), "severities": list({msg.severity for msg in messages})})
```

## HOW — mypy/runners.py

Remove `import structlog` and `structured_logger = ...`.

Convert 4 calls:
```python
# structured_logger.warning("Target directory not found", directory=...)
logger.warning("Target directory not found", extra={"directory": directory})

# structured_logger.info("Starting mypy check", project_dir=..., strict=..., ...)
logger.info("Starting mypy check", extra={"project_dir": project_dir, "strict": strict, "targets": mypy_targets, "command": " ".join(command)})

# structured_logger.warning("Mypy returned configuration error", return_code=..., ...)
logger.warning("Mypy returned configuration error", extra={"return_code": result.return_code, "stdout_length": len(result.stdout), "stderr_length": len(result.stderr), "command": " ".join(command)})

# structured_logger.info("Mypy check completed", return_code=..., total_messages=..., errors=...)
logger.info("Mypy check completed", extra={"return_code": result.return_code, "total_messages": len(messages), "errors": errors_found})
```

## HOW — pytest/runners.py

Remove `import structlog` and `structured_logger = ...`.

Convert 7 calls in `run_tests()` and `check_code_with_pytest()`:
```python
# structured_logger.info("Starting pytest execution", project_dir=..., ...)
logger.info("Starting pytest execution", extra={"project_dir": project_dir, "test_folder": test_folder, "markers": markers, "verbosity": verbosity, "venv_path": venv_path})

# structured_logger.warning("Detected nested pytest execution", depth=..., ...)
logger.warning("Detected nested pytest execution", extra={"depth": os.environ.get("PYTEST_SUBPROCESS_DEPTH"), "project_dir": project_dir})

# structured_logger.info("Pytest execution completed successfully", passed=..., ...)
logger.info("Pytest execution completed successfully", extra={"passed": ..., "failed": ..., "errors": ..., "skipped": ..., "duration": ...})

# structured_logger.error("Pytest execution failed", error=..., ...)
logger.error("Pytest execution failed", extra={"error": str(e), "error_type": type(e).__name__, "project_dir": project_dir, "command": command_line})

# structured_logger.info("Starting pytest code check", ...)
logger.info("Starting pytest code check", extra={"project_dir": project_dir, "test_folder": test_folder, "markers": markers, "verbosity": verbosity})

# structured_logger.info("Pytest code check completed", ...)
logger.info("Pytest code check completed", extra={"passed": ..., "failed": ..., "errors": ..., "skipped": ...})

# structured_logger.error("Pytest code check failed", ...)
logger.error("Pytest code check failed", extra={"error": str(e), "error_type": type(e).__name__, "project_dir": project_dir, "test_folder": test_folder})
```

Also fix any f-string log calls (e.g., `logger.debug(f"Running command: {' '.join(command)}")` → `logger.debug("Running command: %s", " ".join(command))`).

## VERIFICATION

- Run pylint, pytest (unit), mypy — all must pass
- Grep for `structlog` across all source files except `log_utils.py` — should return zero matches
- This is the final module cleanup step

## LLM Prompt

```
Read pr_info/steps/summary.md for context, then implement pr_info/steps/step_6.md.

Migrate the last 3 files to stdlib-only logging:
- src/mcp_tools_py/code_checker_mypy/parsers.py (2 calls)
- src/mcp_tools_py/code_checker_mypy/runners.py (4 calls)
- src/mcp_tools_py/code_checker_pytest/runners.py (7 calls)

For each file:
1. Remove `import structlog` and `structured_logger = ...`
2. Convert all structured_logger calls to logger calls with extra={} dicts
3. Fix any f-string log calls to use lazy %s formatting
4. This is the last cleanup step — after this, verify no module except log_utils.py imports structlog

After editing, run all three code quality checks (pylint, pytest unit tests, mypy).
Commit with a message like: "chore: migrate mypy and pytest modules to stdlib-only logging"
```
