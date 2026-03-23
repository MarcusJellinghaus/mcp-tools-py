# Issue #108: Add Python Refactoring Tools (rope + jedi)

## Summary

Add 5 MCP tools for Python refactoring powered by `rope` (move/rename operations) and `jedi` (symbol discovery and reference finding). The primary use case is splitting large Python files into smaller modules while automatically updating imports project-wide.

### New Tools

| Tool | Library | Purpose |
|------|---------|---------|
| `list_symbols(file)` | jedi | List top-level functions, classes, variables in a file |
| `find_references(file, symbol_name)` | jedi | Find all usages of a symbol across the project |
| `move_symbol(source_file, symbol_name, dest_file, dry_run)` | rope | Move a symbol to another module, update imports |
| `rename(file, symbol_name, new_name, dry_run)` | rope | Rename a symbol project-wide |
| `move_module(source_module, dest_package, dry_run)` | rope | Move an entire module to a new package |

---

## Architectural / Design Changes

### 1. Architecture Layer Rename

`checker_implementation` → `tool_implementation` in both `tach.toml` and `.importlinter`. This reflects that the layer now contains both checker tools and refactoring tools — not just checkers.

### 2. Server Refactor: Thin Orchestrator Pattern

**Before:** `server.py` contains `CodeCheckerServer` with `_register_tools()` holding all 3 checker tool definitions inline (~300 lines of tool code + formatting).

**After:** `server.py` becomes a thin orchestrator:
- `CheckerTools` class (new file `checker_tools.py`) — owns the 3 existing checker tool registrations + formatting methods
- `RefactoringTools` class (in `refactoring/__init__.py`) — owns the 5 new refactoring tool registrations
- `CodeCheckerServer.__init__()` calls `CheckerTools(self).register(self.mcp)` and `RefactoringTools(self.project_dir).register(self.mcp)`

The `CheckerTools` class receives a reference to the server instance (for `_resolved_python`, `_tool_availability`, `project_dir`, etc.) and registers tools on the `mcp` server. No base class needed.

### 3. New Module: `refactoring/`

Flat structure — no models/parsers/runners pattern (rope/jedi are library calls, not subprocesses):

```
src/mcp_tools_py/refactoring/
├── __init__.py       # RefactoringTools class + public API
├── jedi_tools.py     # list_symbols(), find_references()
└── rope_tools.py     # move_symbol(), rename(), move_module()
```

### 4. Key Design Decisions

- **Fresh rope Project per call** — avoids stale state from LLM edits between calls
- **All paths relative to project root** — no absolute paths in input/output
- **No auto-formatting** — caller runs `format_all` per existing workflow
- **Rope's own API for offset resolution** — no cross-dependency between rope_tools and jedi_tools
- **Descriptive errors with hints** — e.g., list available symbols when symbol not found
- **Dry-run support** — `[DRY RUN] Would modify: ...` vs `Modified: ...`
- **Windows compatibility** — use `Path` objects for all path operations; rope and jedi may require forward-slash paths internally

---

## `.importlinter` Layer Ordering

The exact layer ordering for the layers contract:

```
mcp_tools_py.main
mcp_tools_py.server
mcp_tools_py.checker_tools | mcp_tools_py.refactoring | mcp_tools_py.code_checker_pytest | mcp_tools_py.code_checker_pylint | mcp_tools_py.code_checker_mypy
mcp_tools_py.utils
mcp_tools_py.log_utils
```

Both `checker_tools` and `refactoring` are included in the forbidden-imports contract.

---

## Files Created / Modified

### New Files

| File | Purpose |
|------|---------|
| `src/mcp_tools_py/checker_tools.py` | Extracted `CheckerTools` class (checker tool registrations + formatting) |
| `src/mcp_tools_py/refactoring/__init__.py` | `RefactoringTools` class + public API |
| `src/mcp_tools_py/refactoring/jedi_tools.py` | `list_symbols()`, `find_references()` |
| `src/mcp_tools_py/refactoring/rope_tools.py` | `move_symbol()`, `rename_symbol()`, `move_module()` |
| `tests/test_refactoring/__init__.py` | Test package |
| `tests/test_refactoring/test_jedi_tools.py` | Tests for jedi tools |
| `tests/test_refactoring/test_rope_tools.py` | Tests for rope tools |
| `tests/test_refactoring/test_refactoring_tools.py` | Tests for RefactoringTools registration |
| `tests/test_checker_tools.py` | Tests for extracted CheckerTools class |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `rope` and `jedi` to core dependencies |
| `tach.toml` | Rename layer `checker_implementation` → `tool_implementation`; add `mcp_tools_py.refactoring` module; add `mcp_tools_py.checker_tools` module; server LOSES three `code_checker_*` deps, GAINS `checker_tools` and `refactoring` |
| `.importlinter` | Add `mcp_tools_py.refactoring` and `mcp_tools_py.checker_tools` to layer contract and forbidden-imports contract |
| `.gitignore` | Add `.ropeproject/` |
| `src/mcp_tools_py/server.py` | Slim down to thin orchestrator — delegate to `CheckerTools` and `RefactoringTools` |

---

## Implementation Steps (5 Steps, 5 Commits)

| Step | Scope | Risk | Commit |
|------|-------|------|--------|
| **1** | Scaffolding: add deps, create `refactoring/` skeleton, rename architecture layer, update `.gitignore` | Low (additive, no code changes) | `feat: add dependencies and scaffold refactoring module (#108)` |
| **2** | Extract `CheckerTools` from `server.py`, wire into server, update tach/importlinter | Medium (touches working code) | `refactor: extract CheckerTools from server.py (#108)` |
| **3** | Jedi tools: `list_symbols` + `find_references` in `jedi_tools.py`, register via `RefactoringTools` | Low (read-only) | `feat: add list_symbols and find_references tools (#108)` |
| **4** | Rope tools: `move_symbol` + `rename` + `move_module` in `rope_tools.py`, register via `RefactoringTools` | Higher (writes files) | `feat: add move_symbol, rename, and move_module tools (#108)` |
| **5** | Integration tests: end-to-end test moving a function between modules, verifying imports updated | Low (additive) | `test: add end-to-end refactoring integration tests (#108)` |

See `step_1.md` through `step_5.md` for detailed implementation instructions.
