# Step 3: Migrate subprocess_runner.py to stdlib-only logging

> **Reference:** See `pr_info/steps/summary.md` for full context.

## Goal

Remove structlog from the subprocess runner utility. This module has 8 structured_logger calls, mostly for debug/warning/error in subprocess lifecycle events.

## WHERE

- `src/mcp_tools_py/utils/subprocess_runner.py`

## WHAT

No new functions. Transform existing log calls.

## HOW

Remove:
```python
import structlog
structured_logger = structlog.get_logger(__name__)
```

Convert all `structured_logger.*` calls to `logger.*` with `extra={}`:

```python
# BEFORE:
structured_logger.warning("Killing timed out process", pid=popen_proc.pid, command=command[:3])
# AFTER:
logger.warning("Killing timed out process", extra={"pid": popen_proc.pid, "command": command[:3] if command else None})

# BEFORE:
structured_logger.debug("Taskkill failed, using fallback", error=str(e), pid=popen_proc.pid)
# AFTER:
logger.debug("Taskkill failed, using fallback", extra={"error": str(e), "pid": popen_proc.pid})

# BEFORE:
structured_logger.debug("Starting subprocess execution", command=..., cwd=..., ...)
# AFTER:
logger.debug("Starting subprocess execution", extra={"command": command[:3] if command else None, "cwd": options.cwd, "timeout_seconds": options.timeout_seconds, "use_isolation": use_isolation})

# BEFORE:
structured_logger.error("Subprocess execution failed", error=str(e), error_type=..., command_preview=...)
# AFTER:
logger.error("Subprocess execution failed", extra={"error": str(e), "error_type": type(e).__name__, "command_preview": command[:3] if command else None})
```

Apply the same pattern to all 8 occurrences. Key rules:
- `structured_logger.X("message", key=val)` → `logger.X("message", extra={"key": val})`
- Use lazy `%s` formatting where the message itself has variables (but most are static strings here)
- No f-strings in log calls

## VERIFICATION

- Run pylint, pytest (unit), mypy — all must pass
- Grep for `structlog` in subprocess_runner.py — should return zero matches
- test_subprocess_runner.py must still pass

## LLM Prompt

```
Read pr_info/steps/summary.md for context, then implement pr_info/steps/step_3.md.

Migrate utils/subprocess_runner.py to stdlib-only logging:
1. Remove `import structlog` and `structured_logger = ...`
2. Convert all 8 structured_logger calls to logger calls with extra={} dicts
3. Use lazy %s formatting, not f-strings
4. Keep the same log levels (warning, debug, error) as the original calls

After editing, run all three code quality checks (pylint, pytest unit tests, mypy).
Commit with a message like: "chore: migrate subprocess_runner.py to stdlib-only logging"
```
