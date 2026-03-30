# Step 2: Update All 4 Log Sites to Use `format_command()`

> **Context**: See `pr_info/steps/summary.md` for issue overview.
> **Depends on**: Step 1 (`format_command()` exists and is tested).

## Goal

Replace all `command[:3]` log patterns with `format_command(command)` and
enhance the ERROR log site to include `command=` and `cwd=`.

## WHERE

- **Modify**: `src/mcp_tools_py/utils/subprocess_runner.py` (4 log sites)
- **Modify**: `tests/test_subprocess_runner.py` (add log-output assertions)

## WHAT

### Log Site 1 — `_run_subprocess`, STDIO isolation timeout WARNING

```python
# BEFORE:
cmd_display = " ".join(command[:3]) + ("..." if len(command) > 3 else "")
logger.warning(f"Killing timed out process (STDIO isolation, PID: {popen_proc.pid}): "
               f"command='{cmd_display}', ...")

# AFTER:
logger.warning(f"Killing timed out process (STDIO isolation, PID: {popen_proc.pid}): "
               f"command='{format_command(command)}', ...")
```

### Log Site 2 — `_run_subprocess`, regular execution timeout WARNING

```python
# BEFORE:
cmd_display = " ".join(command[:3]) + ("..." if len(command) > 3 else "")
logger.warning(f"Killing timed out process (regular execution, PID: {popen_proc.pid}): "
               f"command='{cmd_display}', ...")

# AFTER:
logger.warning(f"Killing timed out process (regular execution, PID: {popen_proc.pid}): "
               f"command='{format_command(command)}', ...")
```

### Log Site 3 — `execute_subprocess`, DEBUG at start

```python
# BEFORE:
logger.debug(f"Starting subprocess execution: {command[:3] if command else None}")

# AFTER:
logger.debug(f"Starting subprocess execution: {format_command(command)}")
```

### Log Site 4 — `execute_subprocess`, ERROR on failure

```python
# BEFORE:
logger.error(f"Subprocess execution failed: {type(e).__name__}: {e}")

# AFTER:
logger.error(f"Subprocess execution failed: {type(e).__name__}: {e}, "
             f"command='{format_command(command)}', cwd='{options.cwd or 'current'}'")
```

## HOW

- Remove the two `cmd_display = ...` local variable assignments (sites 1 & 2)
- Replace `cmd_display` references with `format_command(command)` inline
- No new imports needed (format_command is already in the same module)

## TESTS

Add a `TestLogOutput` class (or extend existing tests) that:
- Patches `logger` and verifies the DEBUG log at execution start contains the full command
- Verifies the ERROR log on failure includes `command=` and `cwd=`

## DATA

No new data structures. Log messages are strings only.

## Commit

One commit: `Use format_command() in all subprocess log sites (#96)`

---

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_2.md.

Implement Step 2 of issue #96: Update all 4 log sites in subprocess_runner.py
to use format_command().

1. Update all 4 log sites as specified in step_2.md
2. Add tests verifying DEBUG and ERROR log messages contain full command info
3. Run all three quality checks (pylint, pytest, mypy)
4. Commit when all checks pass

The format_command() function from Step 1 must already exist.
```
