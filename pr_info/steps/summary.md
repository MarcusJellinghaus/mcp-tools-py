# Issue #136: Use pyproject.toml auto-detection for target_directories in checker tools

## Summary

Migrate pylint, mypy, and vulture checker tools to use the shared `get_target_directories()` utility from `utils/project_config.py`, replacing hardcoded `["src", "tests"]` defaults. Extract vulture logic into its own runner module for architectural consistency.

## Architectural / Design Changes

### Before
- **Pylint runner** (`code_checker_pylint/runners.py`): hardcodes `["src"]` + conditional `["tests"]` as fallback when `target_directories is None`
- **Mypy runner** (`code_checker_mypy/runners.py`): hardcodes `["src", "tests"]` with existence checks as fallback
- **Vulture**: all logic lives inline in `checker_tools.py` — no runner module — with same hardcoded fallback
- Each tool independently reimplements the same directory resolution logic

### After
- **Directory resolution moves to the registration layer** (`checker_tools.py`), matching the existing formatter pattern in `formatter_tools.py`
- A single shared helper `resolve_target_directories()` in `utils/project_config.py` wraps `get_target_directories()` with warning logging and `ValueError` handling
- **Runners always receive explicit directories** — no more `None` defaults or fallback logic in runners
- **New `code_checker_vulture/` module** with `runners.py` extracts vulture subprocess logic from `checker_tools.py`
- `tach.toml` updated with new module boundary

### Design Pattern (from `formatter_tools.py`)
```
checker_tools.py (registration layer)
  └── resolve_target_directories(project_dir, target_directories)
        ├── target_directories provided → return as-is
        └── None → get_target_directories(project_dir)
              ├── success → log warnings, return dirs
              └── ValueError → return error string
```

Callers check `isinstance(result, str)` for error; otherwise receive `list[str]`.

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `src/mcp_tools_py/utils/project_config.py` | **Modified** | Add `resolve_target_directories()` helper |
| `src/mcp_tools_py/code_checker_vulture/__init__.py` | **Created** | New module init (empty) |
| `src/mcp_tools_py/code_checker_vulture/runners.py` | **Created** | Extracted vulture runner logic |
| `src/mcp_tools_py/checker_tools.py` | **Modified** | Use `resolve_target_directories()` for all 3 tools; call vulture runner |
| `src/mcp_tools_py/code_checker_pylint/runners.py` | **Modified** | Remove fallback logic, make `target_directories` required (`list[str]`) |
| `src/mcp_tools_py/code_checker_mypy/runners.py` | **Modified** | Remove fallback logic, make `target_directories` required (`list[str]`) |
| `src/mcp_tools_py/code_checker_pylint/reporting.py` | **Modified** | Update `get_pylint_prompt` signature: `target_directories` becomes `list[str]` |
| `src/mcp_tools_py/code_checker_mypy/reporting.py` | **Modified** | Update `get_mypy_prompt` signature: `target_directories` becomes `list[str]` |
| `src/mcp_tools_py/formatter/formatter_tools.py` | **Modified** | Replace inline directory resolution with `resolve_target_directories()` |
| `tach.toml` | **Modified** | Add `code_checker_vulture` module + dependency from `checker_tools` |
| `tests/test_project_config.py` | **Modified** | Add tests for `resolve_target_directories()` |
| `tests/test_checker_tools.py` | **Modified** | Update vulture tests for runner extraction; add auto-detection tests for all 3 tools |
| `tests/test_code_checker_vulture/__init__.py` | **Created** | New test module init |
| `tests/test_code_checker_vulture/test_runners.py` | **Created** | Unit tests for vulture runner |

## Implementation Steps Overview

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Add `resolve_target_directories()` helper + tests | `refactor: add shared resolve_target_directories helper` |
| 2 | Create `code_checker_vulture/` runner module + tests | `refactor: extract vulture runner into code_checker_vulture module` |
| 3 | Wire up all 3 tools in `checker_tools.py` + update runners + update tests | `refactor: use pyproject.toml auto-detection in checker tools` |
