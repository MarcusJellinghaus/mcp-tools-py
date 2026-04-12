# Summary: Adopt mcp-coder-utils (subprocess_runner + log_utils)

**Issue:** #152
**Branch:** `adopt/mcp-coder-utils`

## Goal

Replace local copies of `subprocess_runner` and `log_utils` with imports from the shared `mcp-coder-utils` package. The dependency is already in `pyproject.toml`.

## Architectural / Design Changes

### Before
```
mcp_tools_py.log_utils          ← full implementation (setup_logging, log_function_call)
mcp_tools_py.utils.subprocess_runner  ← full implementation (~500 lines)
```
Both are **internal modules** within this project, tested locally, and declared as import-linter layers.

### After
```
mcp_coder_utils.log_utils            ← shared library (source of truth)
mcp_coder_utils.subprocess_runner     ← shared library (source of truth)

mcp_tools_py.log_utils               ← thin re-export shim (safety net)
mcp_tools_py.utils.subprocess_runner  ← thin re-export shim (safety net)
```

- **Primary import path** for all source and test files becomes `mcp_coder_utils.*`
- **Local modules** become thin shims that re-export from the shared library
- **import-linter**: `mcp_tools_py.log_utils` is removed as a layer (external dep can't be a layer); `mcp_tools_py.utils` layer stays (still has `file_utils.py`, `project_config.py`)
- **mypy**: The `warn_unused_ignores = false` override for `mcp_tools_py.utils.subprocess_runner` is removed (mypy doesn't type-check installed packages)
- **Tests**: Local unit tests for both modules are deleted (shared library owns its tests)

### Dependency direction change
```
Before:  checker modules → mcp_tools_py.utils.subprocess_runner (local)
After:   checker modules → mcp_coder_utils.subprocess_runner (external package)
         mcp_tools_py.utils.subprocess_runner → mcp_coder_utils.subprocess_runner (shim)
```

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/log_utils.py` | Replace implementation with re-export shim |
| `src/mcp_tools_py/utils/subprocess_runner.py` | Replace implementation with re-export shim |
| `src/mcp_tools_py/checker_tools.py` | Update imports |
| `src/mcp_tools_py/main.py` | Update imports |
| `src/mcp_tools_py/server.py` | Update imports |
| `src/mcp_tools_py/utility_tools.py` | Update imports |
| `src/mcp_tools_py/inspect_library.py` | Update imports |
| `src/mcp_tools_py/formatter/formatter_tools.py` | Update imports |
| `src/mcp_tools_py/formatter/black_runner.py` | Update imports |
| `src/mcp_tools_py/formatter/isort_runner.py` | Update imports |
| `src/mcp_tools_py/code_checker_pytest/runners.py` | Update imports |
| `src/mcp_tools_py/code_checker_pylint/runners.py` | Update imports |
| `src/mcp_tools_py/code_checker_mypy/runners.py` | Update imports |
| `src/mcp_tools_py/code_checker_ruff/runners.py` | Update imports |
| `src/mcp_tools_py/code_checker_bandit/runners.py` | Update imports |
| `src/mcp_tools_py/code_checker_vulture/runners.py` | Update imports |
| `src/mcp_tools_py/refactoring/rope_tools.py` | Update imports |
| `src/mcp_tools_py/code_checker_pylint/reporting.py` | Update imports |
| `src/mcp_tools_py/code_checker_pytest/reporting.py` | Update imports |
| `src/mcp_tools_py/refactoring/__init__.py` | Update imports |
| `tests/conftest.py` | Update imports |
| `tests/test_error_transparency.py` | Update imports |
| `tests/test_tool_availability.py` | Update imports |
| `tests/test_black_runner.py` | Update imports |
| `tests/test_isort_runner.py` | Update imports |
| `.importlinter` | Remove `mcp_tools_py.log_utils` layer |
| `pyproject.toml` | Remove mypy override for subprocess_runner |

## Files Deleted

| File | Reason |
|------|--------|
| `tests/test_subprocess_runner.py` | Shared library has its own tests |
| `tests/test_log_utils.py` | Shared library has its own tests |

## Steps

1. [Step 1](step_1.md) — Replace `subprocess_runner` imports + create shim
2. [Step 2](step_2.md) — Replace `log_utils` imports + create shim
3. [Step 3](step_3.md) — Delete local tests + update config files + stale-import grep
