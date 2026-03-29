# Step 5: Migrate pylint modules to stdlib-only logging

> **Reference:** See `pr_info/steps/summary.md` for full context.

## Goal

Remove structlog from the pylint checker package: parsers.py (5 calls), runners.py (5 calls), reporting.py (4 calls).

## WHERE

- `src/mcp_tools_py/code_checker_pylint/parsers.py`
- `src/mcp_tools_py/code_checker_pylint/runners.py`
- `src/mcp_tools_py/code_checker_pylint/reporting.py`

## WHAT

No new functions. Transform existing log calls.

## HOW — parsers.py

Remove `import structlog` and `structured_logger = ...`.

Convert 5 calls:
```python
# structured_logger.info("Pylint produced no output")
logger.info("Pylint produced no output")

# structured_logger.error("Invalid pylint output format", output_type=...)
logger.error("Invalid pylint output format", extra={"output_type": type(pylint_output).__name__})

# structured_logger.debug("Successfully parsed pylint JSON output", json_array_length=..., first_item_keys=...)
logger.debug("Successfully parsed pylint JSON output", extra={"json_array_length": len(pylint_output), "first_item_keys": list(pylint_output[0].keys()) if pylint_output else None})

# structured_logger.warning("Skipping non-dict item...", item_type=...)
logger.warning("Skipping non-dict item in pylint output", extra={"item_type": type(item).__name__})

# structured_logger.error("JSON parse error", error=..., output_length=..., output_preview=...)
logger.error("JSON parse error", extra={"error": str(e), "output_length": len(raw_output), "output_preview": raw_output[:100]})
```

## HOW — runners.py

Remove `import structlog` and `structured_logger = ...`.

Convert 5 calls — same pattern:
```python
# structured_logger.warning("Target directory does not exist...", directory=..., full_path=...)
logger.warning("Target directory does not exist, skipping", extra={"directory": directory, "full_path": full_path})

# structured_logger.error("No valid directories to analyze", ...)
logger.error("No valid directories to analyze", extra={"target_directories": target_directories, "project_dir": project_dir})

# structured_logger.info("Starting pylint analysis", ...)
logger.info("Starting pylint analysis", extra={"project_dir": project_dir, "extra_args": extra_args, "target_directories": valid_directories})

# structured_logger.info("Pylint subprocess completed", ...)
logger.info("Pylint subprocess completed", extra={"return_code": subprocess_result.return_code, ...})

# structured_logger.info("Pylint analysis completed", ...)
logger.info("Pylint analysis completed", extra={"return_code": ..., "messages_count": ..., "unique_codes": ...})
```

## HOW — reporting.py

Remove `import structlog` and `structured_logger = ...`.

Convert 4 calls:
```python
# structured_logger.info("Starting pylint prompt generation", ...)
logger.info("Starting pylint prompt generation", extra={"project_dir": project_dir, "extra_args": extra_args})

# structured_logger.error("Pylint execution error detected", ...)
logger.error("Pylint execution error detected", extra={"error": pylint_results.error, "return_code": pylint_results.return_code})

# structured_logger.info("No pylint issues found", ...)
logger.info("No pylint issues found", extra={"project_dir": project_dir})

# structured_logger.info("Pylint issues found, generating prompt", ...)
logger.info("Pylint issues found, generating prompt", extra={"total_codes": total_types, "max_issues": max_issues})
```

## VERIFICATION

- Run pylint, pytest (unit), mypy — all must pass
- Grep for `structlog` in all 3 files — should return zero matches

## LLM Prompt

```
Read pr_info/steps/summary.md for context, then implement pr_info/steps/step_5.md.

Migrate 3 pylint module files to stdlib-only logging:
- src/mcp_tools_py/code_checker_pylint/parsers.py (5 calls)
- src/mcp_tools_py/code_checker_pylint/runners.py (5 calls)  
- src/mcp_tools_py/code_checker_pylint/reporting.py (4 calls)

For each file:
1. Remove `import structlog` and `structured_logger = ...`
2. Convert all structured_logger calls to logger calls with extra={} dicts
3. Use lazy %s formatting, not f-strings

After editing, run all three code quality checks (pylint, pytest unit tests, mypy).
Commit with a message like: "chore: migrate pylint modules to stdlib-only logging"
```
