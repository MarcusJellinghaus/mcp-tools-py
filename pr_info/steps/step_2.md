# Step 2: Refactor existing functions to use new code + test cleanup

> **Read `pr_info/steps/summary.md` first for full context.**
> **Step 1 must be completed before this step.**

## Goal

Wire `prepare_env()` into `_run_subprocess()` (fixing the env inheritance bug), sync
remaining differences with upstream, remove `structlog` dependency, update and clean up
tests.

## Changes

### WHERE: `src/mcp_tools_py/utils/subprocess_runner.py`

#### WHAT: Remove unused imports

```python
# REMOVE these:
from typing import Any, Callable       # → keep only: from typing import Any (if needed, or remove entirely)
import structlog                        # → remove
from mcp_tools_py.log_utils import log_function_call  # → remove
```

Remove `structured_logger = structlog.get_logger(__name__)` variable.

#### WHAT: Replace `structlog` calls with stdlib `logging`

All `structured_logger.warning(...)`, `structured_logger.debug(...)`,
`structured_logger.error(...)` calls → use `logger.warning(...)`, `logger.debug(...)`,
`logger.error(...)` with stdlib formatting (f-strings or %-style).

#### WHAT: Remove `_safe_preexec_fn()`

Delete the entire function. It's replaced by `start_new_session=True` (thread-safe).

#### WHAT: Update `_run_subprocess()`

**Replace inline env logic:**

```python
# BEFORE (buggy):
env = options.env or os.environ.copy()
if is_python_command(command):
    env = get_python_isolation_env()
    if options.env:
        env.update(options.env)

# AFTER (delegates to prepare_env):
env = prepare_env(command, options.env, options.env_remove)
```

**Remove `preexec_fn`** from all `Popen` calls. Keep only `start_new_session`:

```python
# BEFORE:
preexec_fn: Callable[[], Any] | None = None
start_new_session = False
if os.name != "nt":
    preexec_fn = _safe_preexec_fn
    start_new_session = True

# AFTER:
start_new_session = os.name != "nt"
```

Remove `preexec_fn=preexec_fn` from all `Popen()` and `subprocess.run()` calls.

**Add `encoding="utf-8"` and `errors="replace"`** to all `Popen()` calls and to the
`subprocess.run()` call in the no-capture-output branch.

**Add `check=False`** to taskkill `subprocess.run()` calls (don't raise if process
already dead).

**Narrow taskkill exception handler** from `except Exception` to `except OSError` to
match upstream.

**Simplify exception blocks** — the outer try/except around the STDIO isolation branch:

```python
# BEFORE:
except subprocess.TimeoutExpired:
    raise
except Exception:
    if stdout_f and not stdout_f.closed:
        stdout_f.close()
    if stderr_f and not stderr_f.closed:
        stderr_f.close()
    raise

# AFTER (cleanup is in finally, just re-raise):
except Exception:  # pylint: disable=try-except-raise
    raise
```

Same pattern for the regular execution branch.

#### WHAT: Update `execute_subprocess()`

**Narrow exception handling:**

```python
# BEFORE:
except Exception as e:
    # Handle all other exceptions
    ...

# AFTER:
except (FileNotFoundError, PermissionError, OSError) as e:
    # Handle only expected subprocess launch errors
    ...
```

This means `RuntimeError` and other unexpected exceptions now **propagate** instead of
being silently caught.

**Add heartbeat parameters:**

```python
def execute_subprocess(
    command: list[str],
    options: CommandOptions | None = None,
    heartbeat_interval_seconds: int | None = None,
    heartbeat_message: str = "",
) -> CommandResult:
```

```
ALGORITHM (heartbeat integration):
1. If heartbeat_interval_seconds is not None and heartbeat_interval_seconds > 0:
2.   stop_event = threading.Event()
3.   heartbeat_thread = Thread(target=_run_heartbeat, args=(...), daemon=True)
4.   heartbeat_thread.start()
5. ... existing subprocess execution ...
6. In finally block: stop_event.set() to stop heartbeat
```

### WHERE: `src/mcp_tools_py/utils/__init__.py`

#### WHAT: Add new exports

```python
from .subprocess_runner import (
    # ... existing ...
    CalledProcessError,
    SubprocessError,
    TimeoutExpired,
    launch_process,
)
```

Only add `launch_process`, `CalledProcessError`, `SubprocessError`, `TimeoutExpired`.
Do NOT add `prepare_env` or `get_utf8_env` (they're not in upstream's `__all__`).

Update `__all__` list accordingly.

### WHERE: `tests/test_subprocess_runner.py`

#### WHAT: Update imports

Add `_run_subprocess` to imports (for mock-based test).

#### WHAT: Add new test classes

**`TestRunSubprocessUsesPrepareEnv`** — verify `_run_subprocess` delegates to
`prepare_env`:
- `test_run_subprocess_calls_prepare_env` — mock `prepare_env`, run `_run_subprocess`,
  verify mock called with `(command, options.env, options.env_remove)`

**`TestPrepareEnvIntegration`** — real subprocess env inheritance:
- `test_non_python_command_inherits_path` — run a real non-Python command with
  `options.env={"CUSTOM": "val"}`, verify PATH is still available (the actual bug fix)
- `test_python_command_with_env_still_inherits` — same for Python commands

#### WHAT: Update existing test

**`test_execute_command_unexpected_error`** — `RuntimeError` now propagates:

```python
# BEFORE: asserts result.execution_error contains "Unexpected error"
# AFTER:
def test_execute_command_unexpected_error(self) -> None:
    """RuntimeError propagates with narrower exception handling."""
    with patch("subprocess.Popen") as mock_popen:
        mock_popen.side_effect = RuntimeError("Unexpected error")
        with pytest.raises(RuntimeError, match="Unexpected error"):
            execute_subprocess(["test_command"])
```

#### WHAT: Drop low-value tests

Remove these classes/functions entirely:
- `TestCommandResult` — trivial dataclass assertions
- `TestCommandOptions` — trivial dataclass assertions
- `test_sample_command_with_fixture` — fixture smoke test
- `test_command_options_with_fixture` — fixture smoke test
- `test_command_result_creation_with_fixture` — fixture smoke test
- `sample_command` fixture — unused after above removal
- `sample_command_options` fixture — unused after above removal
- `sample_command_result` fixture — unused after above removal

## Verification

After this step:
- The env inheritance bug is fixed
- `subprocess_runner.py` matches upstream (except import paths + CLAUDECODE removal)
- No `structlog` dependency in this module
- All tests pass
- pylint, mypy, pytest all green

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_2.md for full context.
Step 1 is already complete.

Implement Step 2: Refactor existing functions in subprocess_runner.py to use
prepare_env(), remove _safe_preexec_fn, remove structlog, narrow exception handling,
add heartbeat support. Update __init__.py exports. Update and clean up tests.

Key points:
- _run_subprocess: replace inline env logic with prepare_env(command, options.env, options.env_remove)
- Remove _safe_preexec_fn entirely, use start_new_session=True only
- Remove preexec_fn from all Popen/subprocess.run calls
- Add encoding="utf-8", errors="replace" to all Popen calls
- Add check=False to taskkill subprocess.run calls
- execute_subprocess: narrow except Exception → except (FileNotFoundError, PermissionError, OSError)
- execute_subprocess: add heartbeat_interval_seconds and heartbeat_message params
- Replace all structlog calls with stdlib logging
- Remove structlog import, log_function_call import, Callable import
- Update test_execute_command_unexpected_error: RuntimeError now propagates (pytest.raises)
- Add TestRunSubprocessUsesPrepareEnv, TestPrepareEnvIntegration
- Drop TestCommandResult, TestCommandOptions, fixture smoke tests (keep TestConvenienceFunctions)
- Update utils/__init__.py with new exports
- Run format_all.sh, then pylint, pytest (with -m exclusions), mypy
```
