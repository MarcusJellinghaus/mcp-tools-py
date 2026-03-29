# Issue #130: Sync subprocess_runner.py from mcp_coder (env inheritance fix)

## Problem

`_run_subprocess()` has a bug:

```python
env = options.env or os.environ.copy()
```

When `options.env` is provided for **non-Python commands**, it replaces the entire parent
environment — `PATH`, `HOME`, etc. are lost. Python commands are unaffected because
`get_python_isolation_env()` always starts from `os.environ.copy()`.

## Solution

Sync `subprocess_runner.py` from upstream `mcp_coder`. The upstream introduces a
`prepare_env()` function that consolidates environment setup: it always starts from a
base env (`os.environ.copy()`), then merges caller-provided env vars on top.

## Architectural / Design Changes

### Before (current)
- Inline env logic in `_run_subprocess()` — two code paths (Python vs non-Python) with
  the non-Python path having the inheritance bug
- `_safe_preexec_fn()` for Unix process isolation (not thread-safe)
- `structlog` dependency for logging within this module
- Broad `except Exception` catch-all in `execute_subprocess()`

### After (synced)
- **`prepare_env(command, env, env_remove)`** — single consolidated function handles
  both Python and non-Python env setup. Always inherits parent env. Unconditionally
  removes `CLAUDECODE` var (recursion guard for this repo).
- **`get_utf8_env()`** — base env for non-Python commands with UTF-8 encoding and
  platform-specific locale settings
- **`launch_process()`** — fire-and-forget process launcher using `prepare_env()`
- **`_run_heartbeat()`** — daemon thread for periodic logging during long-running
  subprocesses
- **`start_new_session=True`** replaces `_safe_preexec_fn()` (thread-safe)
- **Narrower exception handling** in `execute_subprocess()`:
  `FileNotFoundError | PermissionError | OSError` instead of `Exception`
- **stdlib `logging` only** — no more `structlog` in this module
- **`encoding="utf-8"` + `errors="replace"`** on all `Popen` calls
- **`env_remove`** field on `CommandOptions` for explicit env var removal
- **`__all__`** exports including re-exported subprocess exceptions

### Deviation from upstream
Hardcoded `CLAUDECODE` env var removal in `prepare_env()` — unconditionally remove
after the `env_remove` loop. This is a recursion guard: Claude Code sets this variable
to detect nested invocations. Upstream removed the hardcoded removal (callers pass
`env_remove=["CLAUDECODE"]`), but this repo has no such callers, so unconditional
removal is safer.

## Files to Create or Modify

| File | Action | Purpose |
|------|--------|---------|
| `src/mcp_tools_py/utils/subprocess_runner.py` | **Modify** | Sync from upstream |
| `tests/test_subprocess_runner.py` | **Modify** | Update test suite |
| `src/mcp_tools_py/utils/__init__.py` | **Modify** | Update exports |

No new files or modules are created.

## Implementation Steps

| Step | Summary | Commit |
|------|---------|--------|
| 1 | Add new functions (additive, non-breaking) + their tests | `feat: add prepare_env, get_utf8_env, launch_process, heartbeat` |
| 2 | Refactor existing functions to use new code + test cleanup | `refactor: sync _run_subprocess with upstream, fix env inheritance` |

## Review Checklist (from issue)

After implementation, verify `subprocess_runner.py` is **as identical as possible** to
the mcp_coder upstream version. Allowed differences:
- Import paths (`mcp_tools_py` vs `mcp_coder`)
- Hardcoded `CLAUDECODE` removal in `prepare_env()`
