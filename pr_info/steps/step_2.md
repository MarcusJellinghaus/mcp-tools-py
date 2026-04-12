# Step 2: Replace log_utils imports + create shim

**Ref:** [summary.md](summary.md) | **Issue:** #152 | **Commit:** `adopt: replace log_utils imports with mcp_coder_utils`

## Goal

Replace all `from mcp_tools_py.log_utils import ...` with `from mcp_coder_utils.log_utils import ...`, and convert the local module into a thin re-export shim.

## LLM Prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`.
> Implement step 2: replace all log_utils imports across source files to use `mcp_coder_utils.log_utils`, then convert the local `src/mcp_tools_py/log_utils.py` into a thin re-export shim.
> Run all quality checks (pylint, pytest -n auto excluding integration markers, mypy) and fix any issues.

## WHERE — Files to modify

### Source files (14 import replacements):
1. `src/mcp_tools_py/main.py`
2. `src/mcp_tools_py/server.py`
3. `src/mcp_tools_py/checker_tools.py`
4. `src/mcp_tools_py/utility_tools.py`
5. `src/mcp_tools_py/inspect_library.py`
6. `src/mcp_tools_py/formatter/formatter_tools.py`
7. `src/mcp_tools_py/code_checker_pytest/runners.py`
8. `src/mcp_tools_py/code_checker_pylint/runners.py`
9. `src/mcp_tools_py/code_checker_mypy/runners.py`
10. `src/mcp_tools_py/code_checker_ruff/runners.py`
11. `src/mcp_tools_py/code_checker_bandit/runners.py`
12. `src/mcp_tools_py/log_utils.py` ← becomes shim

Files 13-14: verify by grep — there may be additional source files importing `log_utils` not yet identified. The issue says 14 source + 1 test = 15 total. Grep all `.py` files for `from mcp_tools_py.log_utils` to find any remaining.

### Test files (1):
- `tests/test_log_utils.py` — deleted in step 3, not touched here

### NOT modified:
- `tests/test_log_utils.py` — deleted in step 3

## WHAT — Changes per file

### Import replacement (13+ files)

Each file: replace `from mcp_tools_py.log_utils import X` with `from mcp_coder_utils.log_utils import X`. The imported names stay identical.

### Shim creation: `src/mcp_tools_py/log_utils.py`

Replace the entire implementation with a thin re-export:

```python
"""Logging utilities — thin re-export shim.

All functionality is provided by mcp_coder_utils.log_utils.
This module re-exports the public API for backward compatibility.
"""

from mcp_coder_utils.log_utils import (  # noqa: F401
    log_function_call,
    setup_logging,
)

__all__ = [
    "log_function_call",
    "setup_logging",
]
```

**Note:** The shared `log_utils` also exports `OUTPUT` level, `sensitive_fields`, and redaction features. The shim should re-export the full shared `__all__`. Check the actual `mcp_coder_utils.log_utils.__all__` at implementation time and re-export everything listed there.

## HOW — Integration

- No API changes — `setup_logging` and `log_function_call` signatures are backward-compatible
- Test files that mock `mcp_tools_py.*.log_function_call` still work because mocks target the consumer module
- The shared `log_utils` does NOT suppress noisy third-party loggers (httpx, httpcore). If logging becomes noisy after migration, that's a separate follow-up (add suppression in `main.py`)

## DATA — Return values

No changes to any return values or data structures. This is a pure import-path migration.

## Verification

- [ ] All source files have `from mcp_coder_utils.log_utils import ...`
- [ ] Shim re-exports full shared `__all__`
- [ ] pylint passes
- [ ] pytest passes (unit tests, excluding integration markers)
- [ ] mypy passes
