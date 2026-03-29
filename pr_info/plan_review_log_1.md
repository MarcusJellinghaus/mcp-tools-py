# Plan Review Log — Issue #130

## Round 1 — 2026-03-29

**Findings:**
- Critical: `launch_process` returns `int` (PID) with DEVNULL, not `Popen[str]` with PIPE (resource leak)
- Critical: `_run_heartbeat` interval should be `int`, not `float`; `execute_subprocess` heartbeat params differ
- Critical: `prepare_env` command type should be `list[str] | str`, not `list[str]`
- Critical: `__all__` exports internal helpers not in upstream's `__all__`
- Critical: `get_utf8_env` missing `PYTHONLEGACYWINDOWSFSENCODING` on Windows; Unix differences
- Accept: Plan adds custom timeout message format not in upstream — unnecessary deviation
- Accept: Plan deletes `TestConvenienceFunctions` which tests public `execute_command()` API
- Accept: Missing `encoding`/`errors` on `subprocess.run()` no-capture path
- Accept: `__init__.py` exports plan adds non-public functions
- Accept: Re-export style should use `from subprocess import` not assignment
- Accept: `_run_heartbeat` log format should use minutes/seconds like upstream
- Accept: Taskkill exception handler should narrow to `OSError`
- Skip: Function reordering (harmless, matches upstream)
- Skip: Dropping `TestCommandResult`/`TestCommandOptions` (trivial dataclass tests)
- Skip: Adding `TestMergedUtilities` for moved functions (reasonable)

**Decisions:**
- All 5 Critical: Accept — factual mismatches with upstream, straightforward to fix
- All 7 Accept: Accept — all are upstream alignment fixes, no design questions
- All 3 Skip: Skip — cosmetic or reasonable as-is

**User decisions:** None needed — all findings are factual upstream alignment

**Changes:** Updated `summary.md`, `step_1.md`, `step_2.md` to match upstream signatures, types, exports, and behavior. Created `Decisions.md` log.

**Status:** Committed
