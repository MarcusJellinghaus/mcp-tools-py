# Step 4: Migrate checker_tools.py to stdlib-only logging

> **Reference:** See `pr_info/steps/summary.md` for full context.

## Goal

Remove structlog from the checker tools module. This is the largest migration — 17 structured_logger calls across 5 tool registration methods (pylint, pytest, mypy, lint-imports, vulture).

## WHERE

- `src/mcp_tools_py/checker_tools.py`

## WHAT

No new functions. Transform existing log calls.

## HOW

Remove:
```python
import structlog
structured_logger = structlog.get_logger(__name__)
```

The pattern is the same for every checker method. Each has:
1. A `logger.info(f"Running X check on...")` + `structured_logger.info("Starting X check", ...)` pair at the start → merge into one
2. A `structured_logger.info("X check completed", ...)` at the end → convert to `logger.info`
3. A `logger.error(f"Error running X: ...")` + `structured_logger.error("X check failed", ...)` pair in except → merge into one

Consolidation pattern for each checker:
```python
# BEFORE (start of each checker):
logger.info(f"Running pylint check on project directory: {self._server.project_dir}")
structured_logger.info("Starting pylint check", project_dir=str(self._server.project_dir), extra_args=extra_args)
# AFTER:
logger.info("Starting pylint check", extra={"project_dir": str(self._server.project_dir), "extra_args": extra_args})

# BEFORE (end of each checker):
structured_logger.info("Pylint check completed", issues_found=..., result_length=...)
# AFTER:
logger.info("Pylint check completed", extra={"issues_found": pylint_prompt is not None, "result_length": len(result)})

# BEFORE (exception handler):
logger.error(f"Error running pylint check: {str(e)}")
structured_logger.error("Pylint check failed", error=str(e), error_type=type(e).__name__, ...)
# AFTER:
logger.error("Pylint check failed", extra={"error": str(e), "error_type": type(e).__name__, "project_dir": str(self._server.project_dir)})
```

Also fix f-strings in logger calls:
```python
# BEFORE:
logger.info(f"Running pylint check on project directory: {self._server.project_dir}")
# AFTER (merged with structured call, see above)

# BEFORE:
logger.error(f"Error running pylint check: {str(e)}")  
# AFTER (merged with structured call, see above)
```

Apply this same 3-point pattern to all 5 checkers (pylint, pytest, mypy, lint-imports, vulture).

For pytest specifically, also convert the `sanitized.notes` loop and the success/failure logging.

## VERIFICATION

- Run pylint, pytest (unit), mypy — all must pass
- Grep for `structlog` in checker_tools.py — should return zero matches
- test_checker_tools.py must still pass

## LLM Prompt

```
Read pr_info/steps/summary.md for context, then implement pr_info/steps/step_4.md.

Migrate checker_tools.py to stdlib-only logging:
1. Remove `import structlog` and `structured_logger = ...`
2. For each of the 5 checker methods, merge the dual log calls at start/end/exception
3. Convert all structured_logger calls to logger calls with extra={} dicts
4. Replace f-strings in log calls with lazy %s formatting or static messages with extra={}
5. Keep the same log levels as the original calls

After editing, run all three code quality checks (pylint, pytest unit tests, mypy).
Commit with a message like: "chore: migrate checker_tools.py to stdlib-only logging"
```
