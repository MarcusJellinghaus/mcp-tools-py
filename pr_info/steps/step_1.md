# Step 1: Core Logic + Unit Tests (Mocked)

> **Reference**: See `pr_info/steps/summary.md` for full context.

## Goal

Create `src/mcp_tools_py/inspect_library.py` with the `InspectTools` class and core `_get_library_source()` function. Write mocked unit tests that verify all logic paths without depending on real imports.

## LLM Prompt

```
Implement Step 1 of issue #101 (see pr_info/steps/summary.md for context).

Create src/mcp_tools_py/inspect_library.py and tests/test_inspect_library.py (mocked tests only).

Follow the RefactoringTools pattern from src/mcp_tools_py/refactoring/__init__.py:
- InspectTools class with register() method
- TYPE_CHECKING import for FastMCPProtocol
- @mcp.tool() + @log_function_call decorators on the registered tool

The core logic lives in a private _get_library_source(import_path, max_lines) -> str function.

Write mocked unit tests first (TDD), then implement to make them pass.
Run all three code quality checks (pylint, pytest, mypy) after implementation.
Commit: "feat: add get_library_source core logic with mocked unit tests"
```

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/inspect_library.py` | CREATE |
| `tests/test_inspect_library.py` | CREATE |

## WHAT — `inspect_library.py`

### `_get_library_source(import_path: str, max_lines: int = 200) -> str`

Core logic function (not registered as MCP tool — that happens in `register()`).

### `InspectTools` class

```python
class InspectTools:
    def register(self, mcp: "FastMCPProtocol") -> None:
        self._register_get_library_source(mcp)

    def _register_get_library_source(self, mcp: "FastMCPProtocol") -> None:
        @mcp.tool()
        @log_function_call
        def get_library_source(import_path: str, max_lines: int = 200) -> str:
            """..."""
            return _get_library_source(import_path, max_lines)
```

## HOW — Integration Points

- `from mcp_tools_py.log_utils import log_function_call` — decorator
- `TYPE_CHECKING` import: `from mcp_tools_py.server import FastMCPProtocol`
- Standard library only: `importlib`, `inspect`, `types`

## ALGORITHM — `_get_library_source`

```
1. if max_lines < 1: return error message
2. parts = import_path.split(".")
3. for i in range(len(parts), 0, -1):
     try importlib.import_module(".".join(parts[:i]))
     if success: module = result, remaining = parts[i:]; break
4. if no module found: return "Module '{import_path}' not found"
5. obj = module; for attr in remaining: obj = getattr(obj, attr)
   if AttributeError: return error listing available symbols (sorted, capped 50, type-annotated)
6. try: source = inspect.getsource(obj)
   except (TypeError, OSError): return "Source not available for '...' (built-in/C extension)..."
7. lines = source.splitlines()
   if len(lines) > max_lines: truncate + append note
8. return source text
```

## DATA — Return Values

All returns are `str`:

| Case | Format |
|------|--------|
| Success | Raw source code |
| Success + truncated | Source + `"\n... truncated (showing {max_lines} of {N} lines). Use max_lines to see more."` |
| Invalid max_lines | `"max_lines must be a positive integer (>= 1), got: {value}"` |
| Bad module | `"Module '{name}' not found"` |
| Bad symbol | `"'{name}' not found in module '{mod}'.\n\nAvailable symbols:\n  symbol1 (class)\n  symbol2 (function)\n  ..."` |
| Built-in/C ext | `"Source not available for '{name}' (built-in/C extension). Only pure-Python symbols have inspectable source."` |

## TESTS — Mocked Unit Tests

In `tests/test_inspect_library.py`, mock `importlib.import_module` and `inspect.getsource`:

| Test | What it verifies |
|------|-----------------|
| `test_parse_import_path_module_and_attr` | `"a.b.c.D"` → tries `a.b.c.D`, falls back to `a.b.c` + getattr `D` |
| `test_walk_backwards_resolution` | Tries longest path first, falls back correctly |
| `test_truncation_applied` | Source > max_lines → truncated with correct message |
| `test_truncation_not_applied` | Source <= max_lines → full source returned |
| `test_bad_module_error` | All import attempts fail → clear error message |
| `test_bad_symbol_lists_available` | Module found but attr missing → sorted list with types; verify 50-symbol cap behavior |
| `test_builtin_c_extension_error` | `getsource` raises `TypeError` → friendly message |
| `test_max_lines_invalid_returns_error` | `max_lines` in `[0, -5, -1]` → validation error (parameterized test) |
