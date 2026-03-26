# Step 2: Server-level vulture support (binary, availability, whitelist param)

> **Context**: See [summary.md](summary.md) for full architecture overview.

## LLM Prompt

```
Implement Step 2 of Issue #124 (see pr_info/steps/summary.md for context).

Add vulture support to server.py and create_server():
- Add `vulture_whitelist` init param (default "vulture_whitelist.py"), store as self.vulture_whitelist
- Add vulture binary resolution in _check_tool_availability() following the lint-imports pattern
- Store resolved binary as self._vulture_binary

Update tests in tests/test_tool_availability.py:
- All expected availability dicts must include "vulture": True/False
- Add test for vulture binary available/unavailable (mirror lint-imports tests)

Run all three code quality checks after editing. Fix any issues before committing.
```

## WHERE

- `src/mcp_tools_py/server.py`
- `tests/test_tool_availability.py`

## WHAT — Functions & Signatures

### server.py

**`CodeCheckerServer.__init__`** — add parameter:
```python
def __init__(
    self,
    project_dir: Path,
    python_executable: Optional[str] = None,
    venv_path: Optional[str] = None,
    test_folder: str = "tests",
    keep_temp_files: bool = False,
    refactoring_timeout: int = 120,
    vulture_whitelist: str = "vulture_whitelist.py",  # NEW
) -> None:
```

**`create_server`** — add parameter:
```python
def create_server(
    project_dir: Path,
    ...
    vulture_whitelist: str = "vulture_whitelist.py",  # NEW
) -> CodeCheckerServer:
```

**`_check_tool_availability`** — extend with vulture block (no signature change):
```python
def _check_tool_availability(self) -> dict[str, bool]:
```

### New attributes set in __init__ / _check_tool_availability

- `self.vulture_whitelist: str` — raw whitelist filename
- `self._vulture_binary: Optional[str]` — resolved binary path or None

## HOW — Integration Points

1. Store `self.vulture_whitelist = vulture_whitelist` in `__init__` before `_check_tool_availability()` call
2. In `_check_tool_availability()`, after the lint-imports block, add an identical block for vulture:
   - If `self.venv_path` is set, resolve binary path (`Scripts/vulture.exe` on Windows, `bin/vulture` on Unix)
   - Check `os.path.exists(binary)`
   - Set `self._vulture_binary` and `availability["vulture"]`
3. Pass `vulture_whitelist` through `create_server()` to `CodeCheckerServer()`

## ALGORITHM — _check_tool_availability vulture block

```
if self.venv_path:
    binary = venv_path / ("Scripts/vulture.exe" if nt else "bin/vulture")
    vulture_available = os.path.exists(binary)
else:
    vulture_available = False
    binary = None
self._vulture_binary = binary if vulture_available else None
availability["vulture"] = vulture_available
```

## DATA

- `self._vulture_binary`: `Optional[str]` — full path to vulture binary, or None
- `availability["vulture"]`: `bool` — whether vulture is available
- `self.vulture_whitelist`: `str` — whitelist filename (e.g. `"vulture_whitelist.py"`)

## Tests to update

In `tests/test_tool_availability.py`:
- `TestCheckToolAvailability.test_all_tools_available` — expected dict gets `"vulture": True`
- `TestCheckToolAvailability.test_all_tools_missing` — expected dict gets `"vulture": False`
- `TestCheckToolAvailability.test_one_tool_missing` — assert `"vulture"` key exists
- `TestCheckToolAvailability.test_timed_out_tool_marked_unavailable` — expected dict gets `"vulture": False`
- `TestCheckToolAvailability.test_lint_imports_available_when_binary_exists` — also assert `"vulture"` key
- `TestCheckToolAvailability.test_lint_imports_unavailable_when_no_venv` — also assert `"vulture": False`
- `TestCheckToolAvailability.test_lint_imports_unavailable_when_binary_missing` — also assert `"vulture"` key
- Add new `test_vulture_available_when_binary_exists` and `test_vulture_unavailable_when_no_venv`

## Commit

```
feat(server): add vulture binary resolution and availability check

Part of #124. Adds vulture_whitelist init param, binary lookup in venv
(mirroring lint-imports), and availability tracking.
```
