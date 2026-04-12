# Step 1: Replace subprocess_runner imports + create shim

**Ref:** [summary.md](summary.md) | **Issue:** #152 | **Commit:** `adopt: replace subprocess_runner imports with mcp_coder_utils`

## Goal

Replace all `from mcp_tools_py.utils.subprocess_runner import ...` with `from mcp_coder_utils.subprocess_runner import ...`, and convert the local module into a thin re-export shim.

## LLM Prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_1.md`.
> Implement step 1: replace all subprocess_runner imports across source and test files to use `mcp_coder_utils.subprocess_runner`, then convert the local `src/mcp_tools_py/utils/subprocess_runner.py` into a thin re-export shim.
> Do NOT modify `src/mcp_tools_py/utils/__init__.py` — it imports from the local shim and continues to work.
> Run all quality checks (pylint, pytest -n auto excluding integration markers, mypy) and fix any issues.

## WHERE — Files to modify

### Source files (11 import replacements):
1. `src/mcp_tools_py/checker_tools.py`
2. `src/mcp_tools_py/code_checker_pytest/runners.py`
3. `src/mcp_tools_py/code_checker_pylint/runners.py`
4. `src/mcp_tools_py/code_checker_mypy/runners.py`
5. `src/mcp_tools_py/code_checker_ruff/runners.py`
6. `src/mcp_tools_py/code_checker_bandit/runners.py`
7. `src/mcp_tools_py/code_checker_vulture/runners.py`
8. `src/mcp_tools_py/formatter/black_runner.py`
9. `src/mcp_tools_py/formatter/isort_runner.py`
10. `src/mcp_tools_py/refactoring/rope_tools.py`
11. `src/mcp_tools_py/utils/subprocess_runner.py` ← becomes shim

### Test files (5 import replacements):
1. `tests/conftest.py`
2. `tests/test_error_transparency.py`
3. `tests/test_tool_availability.py`
4. `tests/test_black_runner.py`
5. `tests/test_isort_runner.py`

### NOT modified:
- `src/mcp_tools_py/utils/__init__.py` — imports from `.subprocess_runner` (the local shim), still works
- `tests/test_subprocess_runner.py` — deleted in step 3, not touched here

## WHAT — Changes per file

### Import replacement (15 files)

Each file: replace `from mcp_tools_py.utils.subprocess_runner import X` with `from mcp_coder_utils.subprocess_runner import X`. The imported names stay identical.

### Shim creation: `src/mcp_tools_py/utils/subprocess_runner.py`

Replace the entire ~500-line implementation with a thin re-export:

```python
"""Subprocess execution utilities — thin re-export shim.

All functionality is provided by mcp_coder_utils.subprocess_runner.
This module re-exports the public API for backward compatibility.
"""

from mcp_coder_utils.subprocess_runner import (  # noqa: F401
    CalledProcessError,
    CommandOptions,
    CommandResult,
    MAX_STDERR_IN_ERROR,
    SubprocessError,
    TimeoutExpired,
    check_tool_missing_error,
    execute_command,
    execute_subprocess,
    format_command,
    launch_process,
    prepare_env,
    truncate_stderr,
)

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
    "format_command",
    "launch_process",
    "prepare_env",
    "truncate_stderr",
]
```

## HOW — Integration

- No API changes — all names remain the same
- `utils/__init__.py` imports from `.subprocess_runner` (the shim) — unchanged, still works
- Test files that mock `mcp_tools_py.code_checker_*.runners.execute_command` still work because the mock targets the module where the name is used, not where it's defined

## DATA — Return values

No changes to any return values or data structures. This is a pure import-path migration.

## Verification

- [ ] All 15 files have `from mcp_coder_utils.subprocess_runner import ...`
- [ ] Shim re-exports full shared `__all__` (including `prepare_env` not previously exported locally)
- [ ] pylint passes
- [ ] pytest passes (unit tests, excluding integration markers)
- [ ] mypy passes
