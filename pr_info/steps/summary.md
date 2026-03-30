# Issue #96: Log Full Command at DEBUG Level in subprocess_runner

## Summary

Replace truncated `command[:3]` logging in `subprocess_runner.py` with a full,
platform-aware command string (capped at 200 characters). This improves
developer observability when debugging external tool invocations (pytest, mypy,
pylint, etc.) without changing any tool behavior or output.

## Design Changes

**No architectural changes.** This is a small, self-contained enhancement
within the existing `utils/subprocess_runner.py` module.

### New Public Function

```python
def format_command(command: list[str]) -> str
```

- Uses `shlex.join()` on Unix, `subprocess.list2cmdline()` on Windows
- Truncates at 200 characters with `...` suffix
- Exported in `__all__`

### Log Site Changes (4 total)

| # | Location | Level | Change |
|---|----------|-------|--------|
| 1 | `_run_subprocess` — STDIO isolation timeout | WARNING | `command[:3]` → `format_command(command)` |
| 2 | `_run_subprocess` — regular execution timeout | WARNING | `command[:3]` → `format_command(command)` |
| 3 | `execute_subprocess` — execution start | DEBUG | `command[:3]` → `format_command(command)` |
| 4 | `execute_subprocess` — failure error | ERROR | Add `command=` and `cwd=` to message |

## Files Modified

| File | Action |
|------|--------|
| `src/mcp_tools_py/utils/subprocess_runner.py` | Add `format_command`, update 4 log sites |
| `tests/test_subprocess_runner.py` | Add `TestFormatCommand` test class |

No new files or modules created.

## Implementation Steps

- **Step 1**: Add `format_command()` with tests (TDD)
- **Step 2**: Update all 4 log sites to use `format_command()`
