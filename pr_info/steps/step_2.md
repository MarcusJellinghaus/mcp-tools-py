# Step 2: Migrate main.py and server.py to stdlib-only logging

> **Reference:** See `pr_info/steps/summary.md` for full context.

## Goal

Remove structlog from the entry point and server modules. These have few structured_logger calls (4 and 2 respectively) and are good candidates to migrate first.

## WHERE

- `src/mcp_tools_py/main.py` (4 structured_logger calls)
- `src/mcp_tools_py/server.py` (2 structured_logger calls, uses `logger` name not `stdlogger`)

## WHAT

No new functions. Transform existing log calls.

## HOW — main.py

Remove:
```python
import structlog
structured_logger = structlog.get_logger(__name__)
```

Rename `stdlogger` → `logger` for consistency with other modules:
```python
logger = logging.getLogger(__name__)
```

Consolidate dual calls. For each pair, merge into one stdlib call:

```python
# BEFORE (line ~128-131):
stdlogger.debug("Logger initialized in main")
structured_logger.debug("Structured logger initialized in main", log_level=args.log_level)
# AFTER:
logger.debug("Logger initialized", extra={"log_level": args.log_level})

# BEFORE (line ~133-139):
stdlogger.info("Starting MCP Tools Py server with project directory: %s", project_dir)
if log_file:
    structured_logger.info("Starting MCP Tools Py server", project_dir=str(project_dir), ...)
# AFTER:
logger.info("Starting MCP Tools Py server", extra={"project_dir": str(project_dir), "log_level": args.log_level, "log_file": log_file})

# BEFORE (line ~152-153):
stdlogger.info("Starting MCP server")
structured_logger.info("Starting MCP server")
# AFTER:
logger.info("Starting MCP server")

# BEFORE (line ~154-155):
stdlogger.debug("About to call server.run()")
structured_logger.debug("About to call server.run()", project_dir=str(project_dir))
# AFTER:
logger.debug("About to call server.run()", extra={"project_dir": str(project_dir)})
```

Also remove `from mcp_tools_py.log_utils import setup_logging` import of structlog (setup_logging import stays).

## HOW — server.py

Remove:
```python
import structlog
structured_logger = structlog.get_logger(__name__)
```

Consolidate calls:

```python
# BEFORE (in __init__, ~line 85):
structured_logger.debug("Tool environment resolved", python_executable=..., tool_availability=...)
# AFTER:
logger.debug("Tool environment resolved", extra={"python_executable": self._resolved_python, "tool_availability": self._tool_availability})

# BEFORE (in run(), ~line 152-153):
logger.info("Starting MCP server")
structured_logger.info("Starting MCP server")
# AFTER:
logger.info("Starting MCP server")
```

## DATA

No data structure changes. Same log messages, same information, different mechanism.

## VERIFICATION

- Run pylint, pytest (unit), mypy — all must pass
- Grep for `structlog` in both files — should return zero matches
- Existing tests (test_server_params.py etc.) must still pass

## LLM Prompt

```
Read pr_info/steps/summary.md for context, then implement pr_info/steps/step_2.md.

Migrate main.py and server.py to stdlib-only logging:
1. Remove `import structlog` and `structured_logger = ...` from both files
2. In main.py, rename `stdlogger` to `logger` for consistency
3. Consolidate dual log calls into single stdlib calls using extra={} for structured fields
4. Remove duplicate log calls (where both logger and structured_logger say the same thing)
5. Use lazy %s formatting, not f-strings, in log calls

After editing, run all three code quality checks (pylint, pytest unit tests, mypy).
Commit with a message like: "chore: migrate main.py and server.py to stdlib-only logging"
```
