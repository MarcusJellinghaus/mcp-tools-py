# Step 1: Add lint-imports availability check to `server.py` + tests

> **Context**: See `pr_info/steps/summary.md` for full issue context and architecture.

## Goal

Add `lint-imports` to the startup availability check in `server.py`. Unlike pylint/pytest/mypy (which use `python -m <tool> --version`), lint-imports is checked via **file existence** of the binary in the venv.

## WHERE

- `src/mcp_tools_py/server.py` — modify `_check_tool_availability()`
- `tests/test_tool_availability.py` — update existing assertions, add new tests

## WHAT — Tests (write first)

### 1. Update existing `TestCheckToolAvailability` assertions

Every test that asserts `server._tool_availability == {"pytest": ..., "pylint": ..., "mypy": ...}` must now also include `"lint-imports"`. Specifically:

- `test_all_tools_available` — mock `os.path.exists` to return `True` for the lint-imports binary path (in addition to setting `venv_path` on the server), and expect `"lint-imports": True`
- `test_all_tools_missing` — expect `"lint-imports": False`
- `test_timed_out_tool_marked_unavailable` — expect `"lint-imports": False`

### 2. Add new test: `test_lint_imports_available_when_binary_exists`

```python
def test_lint_imports_available_when_binary_exists(self) -> None:
    """When venv_path is set and lint-imports binary exists, mark available."""
```

- Mock `os.path.exists` to return `True` for the lint-imports binary path
- Mock `os.name` for platform-specific path
- Assert `server._tool_availability["lint-imports"] is True`

### 3. Add new test: `test_lint_imports_unavailable_when_no_venv`

```python
def test_lint_imports_unavailable_when_no_venv(self) -> None:
    """When no venv_path is configured, lint-imports is unavailable."""
```

- Create server without `venv_path`
- Assert `server._tool_availability["lint-imports"] is False`

### 4. Add new test: `test_lint_imports_unavailable_when_binary_missing`

```python
def test_lint_imports_unavailable_when_binary_missing(self) -> None:
    """When venv_path is set but binary doesn't exist, mark unavailable."""
```

- Mock `os.path.exists` to return `True` for python but `False` for lint-imports
- Assert `server._tool_availability["lint-imports"] is False`

## WHAT — Implementation

### Function: `_check_tool_availability()` in `CodeCheckerServer`

**Signature** (unchanged — returns `dict[str, bool]`):
```python
def _check_tool_availability(self) -> dict[str, bool]:
```

**Changes**: After the existing `for tool in [...]` loop, add lint-imports check.

### HOW — Integration

The lint-imports check is appended after the existing loop (no changes to existing logic).

### ALGORITHM (pseudocode)

```
# After existing pytest/pylint/mypy loop:
lint_imports_available = False
if self.venv_path:
    if os.name == "nt":
        binary = os.path.join(self.venv_path, "Scripts", "lint-imports.exe")
    else:
        binary = os.path.join(self.venv_path, "bin", "lint-imports")
    lint_imports_available = os.path.exists(binary)
availability["lint-imports"] = lint_imports_available
if not lint_imports_available:
    logger.warning("lint-imports not found...")
```

### DATA — Return value change

Before: `{"pytest": bool, "pylint": bool, "mypy": bool}`
After: `{"pytest": bool, "pylint": bool, "mypy": bool, "lint-imports": bool}`

## Commit message

```
feat: add lint-imports availability check via file existence
```

## LLM Prompt

```
Implement Step 1 of issue #121 (see pr_info/steps/summary.md for context and pr_info/steps/step_1.md for details).

TDD approach: write/update tests first in tests/test_tool_availability.py, then implement the change in src/mcp_tools_py/server.py.

Key requirements:
- lint-imports availability is checked via file existence (not subprocess)
- Binary path is platform-aware: Scripts/lint-imports (Windows) vs bin/lint-imports (Linux)
- If no venv_path is configured, lint-imports is marked unavailable
- Update all existing assertions that check _tool_availability dict to include "lint-imports"
- Run all three code quality checks (pylint, pytest, mypy) and fix any issues
```
