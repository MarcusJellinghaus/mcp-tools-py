# Step 1: Add new functions (additive, non-breaking) + tests

> **Read `pr_info/steps/summary.md` first for full context.**

## Goal

Add all **new** functions and fields to `subprocess_runner.py` without changing any
existing behavior. This is purely additive — existing code continues to work as before.
Write tests for every new function.

## Changes

### WHERE: `src/mcp_tools_py/utils/subprocess_runner.py`

#### WHAT: New imports

```python
import threading  # for heartbeat
```

Keep existing imports for now (structlog, log_function_call) — they're still used by
existing code and will be removed in step 2.

#### WHAT: Add `__all__` (after logger declarations)

```python
__all__ = [
    "CalledProcessError",
    "CommandOptions",
    "CommandResult",
    "MAX_STDERR_IN_ERROR",
    "SubprocessError",
    "TimeoutExpired",
    "check_tool_missing_error",
    "execute_command",
    "execute_subprocess",
    "get_python_isolation_env",
    "get_utf8_env",
    "is_python_command",
    "launch_process",
    "prepare_env",
    "truncate_stderr",
]

# Re-export subprocess exceptions for callers
CalledProcessError = subprocess.CalledProcessError
SubprocessError = subprocess.SubprocessError
TimeoutExpired = subprocess.TimeoutExpired
```

#### WHAT: Move `check_tool_missing_error()` and `truncate_stderr()` above dataclasses

Move these two functions (and `MAX_STDERR_IN_ERROR`) to right after the `__all__` block
and re-exports, before the `CommandResult` and `CommandOptions` dataclasses. This is an
ordering change to match upstream — no logic changes.

#### WHAT: Add `env_remove` field to `CommandOptions`

```python
@dataclass
class CommandOptions:
    # ... existing fields ...
    env_remove: list[str] | None = None
```

- **DATA**: `list[str] | None`, defaults to `None`
- Add to docstring: "env_remove: List of environment variable names to remove"

#### WHAT: `get_utf8_env() -> dict[str, str]`

New function — base environment for non-Python commands.

```
ALGORITHM:
1. Copy os.environ
2. Set PYTHONIOENCODING=utf-8
3. If Windows: set PYTHONUTF8=1
4. If Unix: set LC_ALL=C.UTF-8, LANG=C.UTF-8
5. Return env dict
```

#### WHAT: `prepare_env(command, env, env_remove) -> dict[str, str]`

Consolidated env setup. This is the **core fix** for the inheritance bug.

```python
def prepare_env(
    command: list[str],
    env: dict[str, str] | None = None,
    env_remove: list[str] | None = None,
) -> dict[str, str]:
```

```
ALGORITHM:
1. If is_python_command(command): base = get_python_isolation_env()
2. Else: base = get_utf8_env()
3. If env provided: base.update(env)  # merge on top
4. If env_remove: for key in env_remove: base.pop(key, None)
5. base.pop("CLAUDECODE", None)  # hardcoded recursion guard (deviation)
6. Return base
```

- **HOW**: Always starts from `os.environ.copy()` (via helper), then merges.
  This fixes the bug — caller env is merged, never replaces.
- **DATA**: Returns `dict[str, str]` with full inherited environment

#### WHAT: `_run_heartbeat(stop_event, interval, message, start_time) -> None`

Daemon thread target for periodic logging during long-running subprocesses.

```python
def _run_heartbeat(
    stop_event: threading.Event,
    interval: float,
    message: str,
    start_time: float,
) -> None:
```

```
ALGORITHM:
1. Loop while not stop_event.is_set():
2.   stop_event.wait(interval)
3.   If stop_event.is_set(): break
4.   elapsed = time.time() - start_time
5.   logger.info(message, elapsed_seconds=elapsed)
```

#### WHAT: `launch_process(command, cwd, shell, env, env_remove) -> subprocess.Popen`

Fire-and-forget process launcher using `prepare_env()`.

```python
def launch_process(
    command: list[str],
    cwd: str | None = None,
    shell: bool = False,
    env: dict[str, str] | None = None,
    env_remove: list[str] | None = None,
) -> subprocess.Popen[str]:
```

```
ALGORITHM:
1. merged_env = prepare_env(command, env, env_remove)
2. start_new_session = (os.name != "nt")
3. Return subprocess.Popen(command, cwd=cwd, shell=shell, env=merged_env,
       start_new_session=start_new_session, stdout=PIPE, stderr=PIPE,
       encoding="utf-8", errors="replace")
```

### WHERE: `tests/test_subprocess_runner.py`

#### WHAT: New test classes

Update imports to include new functions:

```python
from mcp_tools_py.utils.subprocess_runner import (
    # ... existing imports ...
    get_utf8_env,
    launch_process,
    prepare_env,
    _run_heartbeat,
    CalledProcessError,
    SubprocessError,
    TimeoutExpired,
)
```

**`TestPrepareEnv`** — unit tests for `prepare_env()`:
- `test_python_command_uses_isolation_env` — verify Python commands get isolation env
- `test_non_python_command_uses_utf8_env` — verify non-Python gets UTF-8 base env
- `test_caller_env_merged_on_top` — verify `env` dict is merged, not replaced
- `test_env_inherits_parent_path` — verify PATH from parent env is preserved (the bug fix)
- `test_env_remove_keys` — verify `env_remove` removes specified keys
- `test_claudecode_always_removed` — verify CLAUDECODE is unconditionally removed
- `test_env_remove_none_is_noop` — verify None env_remove doesn't error

**`TestCommandOptionsEnvRemove`** — field defaults:
- `test_env_remove_defaults_none` — verify default is None
- `test_env_remove_with_values` — verify setting a list works

**`TestMergedUtilities`** — parametrized tests for `check_tool_missing_error` and
`truncate_stderr`:
- `test_check_tool_missing_found` — parametrize with pytest/pylint/mypy
- `test_check_tool_missing_not_found` — returns None when no match
- `test_truncate_stderr_short` — no truncation needed
- `test_truncate_stderr_long` — truncation with "..."
- `test_truncate_stderr_exact` — exact boundary

**`TestLaunchProcess`** — mock-based:
- `test_launch_process_returns_popen` — verify return type
- `test_launch_process_uses_prepare_env` — mock prepare_env, verify called
- `test_launch_process_passes_cwd_and_shell` — verify args forwarded

**`TestHeartbeat`** — heartbeat thread:
- `test_heartbeat_stops_on_event` — verify thread stops when event set
- `test_heartbeat_logs_at_interval` — verify logger.info called with elapsed time
- `test_heartbeat_handles_exception` — no crash on logger error (if applicable)

## Verification

After this step:
- All existing tests still pass (nothing changed)
- All new tests pass
- pylint, mypy, pytest all green
- `subprocess_runner.py` has new functions but existing code is untouched

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_1.md for full context.

Implement Step 1: Add new functions to subprocess_runner.py (additive only, do not
change existing functions). Then add tests for all new functions.

Key points:
- Add threading import, __all__, re-exported exceptions
- Move check_tool_missing_error and truncate_stderr above dataclasses
- Add env_remove field to CommandOptions
- Add get_utf8_env(), prepare_env(), _run_heartbeat(), launch_process()
- prepare_env() must unconditionally remove CLAUDECODE env var
- Add test classes: TestPrepareEnv, TestCommandOptionsEnvRemove, TestMergedUtilities,
  TestLaunchProcess, TestHeartbeat
- Do NOT modify existing functions — that's step 2
- Run format_all.sh, then pylint, pytest (with -m exclusions), mypy
```
