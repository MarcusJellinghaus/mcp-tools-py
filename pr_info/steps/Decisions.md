# Decisions Log for Issue #130

## 1. `launch_process` returns `int` (PID), not `Popen`
Upstream returns `process.pid` and uses `DEVNULL` for stdout/stderr (fire-and-forget).
Accept `cwd: str | Path | None`.

## 2. `_run_heartbeat` interval is `int`, not `float`
Log format uses minutes/seconds: `logger.info("%s (elapsed: %dm %ds)", message, minutes, seconds)`.

## 3. `prepare_env` accepts `list[str] | str` for command
Add `isinstance(command, list)` guard before calling `is_python_command()`.

## 4. `__all__` excludes internal helpers
Remove `get_python_isolation_env`, `get_utf8_env`, `is_python_command`, `prepare_env`
from `__all__`. Only public API symbols are exported.

## 5. `get_utf8_env` platform details
Windows: also set `PYTHONLEGACYWINDOWSFSENCODING=utf-8`. Unix: set `PYTHONUTF8=1`
(same as Windows) and `LC_ALL=C.UTF-8` only (no `LANG=C.UTF-8`).

## 6. Re-exports use direct imports
Use `from subprocess import CalledProcessError, SubprocessError, TimeoutExpired`
instead of assignment style.

## 7. Keep `TestConvenienceFunctions`
Do NOT delete — it tests the public `execute_command()` API used by multiple callers.

## 8. No improved timeout logging
Keep upstream format: `f"Process timed out after {options.timeout_seconds} seconds"`.
Do not add elapsed-time-based timeout messages.

## 9. `__init__.py` exports limited to `__all__`
Only add `launch_process`, `CalledProcessError`, `SubprocessError`, `TimeoutExpired`.
Do NOT add `prepare_env` or `get_utf8_env`.

## 10. `execute_subprocess` heartbeat defaults
`heartbeat_interval_seconds: int | None = None` (not `float = 0`).
`heartbeat_message: str = ""` (not `"Subprocess still running"`).

## 11. Taskkill exception handler narrowed to `OSError`
Match upstream by using `except OSError` instead of `except Exception`.

## 12. `subprocess.run()` encoding in no-capture branch
Explicitly add `encoding="utf-8"` and `errors="replace"` to the `subprocess.run()`
call in the no-capture-output branch too.
