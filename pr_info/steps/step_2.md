# Step 2: Real-Import Tests + MCP Registration in `server.py`

> **Reference**: See `pr_info/steps/summary.md` for full context.

## Goal

Add real-import unit tests (stdlib + structlog, no markers needed) and wire `InspectTools` into `server.py`.

## LLM Prompt

```
Implement Step 2 of issue #101 (see pr_info/steps/summary.md for context).

1. Add real-import tests to tests/test_inspect_library.py (append to existing file from Step 1).
   These test against actual installed packages (json, builtins, structlog) — no mocking, no markers.

2. Wire InspectTools into src/mcp_tools_py/server.py:
   - Import InspectTools from mcp_tools_py.inspect_library
   - Call InspectTools().register(self.mcp) in CodeCheckerServer.__init__

Run all three code quality checks after implementation.
Commit: "feat: wire get_library_source into MCP server with real-import tests"
```

## WHERE

| File | Action |
|------|--------|
| `tests/test_inspect_library.py` | MODIFY — add real-import test class |
| `src/mcp_tools_py/server.py` | MODIFY — import + register |

## WHAT — `server.py` Changes

```python
# Add import
from mcp_tools_py.inspect_library import InspectTools

# In CodeCheckerServer.__init__, after RefactoringTools registration:
InspectTools().register(self.mcp)
```

## HOW — Integration

- `InspectTools()` takes no constructor args (unlike `CheckerTools(self)` or `RefactoringTools(self.project_dir)`)
- Registration order: `CheckerTools` → `RefactoringTools` → `InspectTools`

## TESTS — Real-Import Tests

Add to `tests/test_inspect_library.py` (no integration markers — stdlib + structlog are always fast & available):

| Test | `import_path` | `max_lines` | Assertion |
|------|--------------|-------------|-----------|
| `test_stdlib_class` | `json.encoder.JSONEncoder` | default | Contains `def encode` |
| `test_module_level` | `json.encoder` | default | Contains `class JSONEncoder` |
| `test_nested_attribute` | `json.encoder.JSONEncoder.encode` | default | Contains `def encode`, shorter than full class |
| `test_custom_max_lines_truncation` | `json.encoder.JSONEncoder` | 50 | Contains `"truncated"` and `"showing 50 of"` |
| `test_bad_module` | `nonexistent_package.Foo` | default | Contains `"not found"` |
| `test_bad_symbol_lists_available` | `json.NoSuchThing` | default | Contains available symbols with types |
| `test_third_party_dep` | `structlog.get_logger` | default | Contains `def get_logger` |
| `test_builtin_type` | `builtins.dict` | default | Contains `"source not available"` and `"built-in/C extension"` |
| `test_invalid_max_lines_zero` | `json.encoder` | 0 | Contains `"positive integer"` |
