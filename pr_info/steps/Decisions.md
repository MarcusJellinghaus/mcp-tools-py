# Decisions Log

## 1. Split Step 1 into scaffolding (Step 1) and CheckerTools extraction (Step 2)

Old Step 1 bundled 4 concerns (scaffolding, config, CheckerTools tests, CheckerTools extraction). Split into two steps: Step 1 is pure scaffolding + config (low risk, additive), Step 2 is the CheckerTools extraction from server.py (medium risk, touches working code). Old Steps 2-4 renumbered to 3-5.

## 2. Explicit `.importlinter` layer ordering

The layers contract must specify the exact layer ordering:
```
mcp_tools_py.main
mcp_tools_py.server
mcp_tools_py.checker_tools | mcp_tools_py.refactoring | mcp_tools_py.code_checker_pytest | mcp_tools_py.code_checker_pylint | mcp_tools_py.code_checker_mypy
mcp_tools_py.utils
mcp_tools_py.log_utils
```
Both `checker_tools` and `refactoring` added to the forbidden-imports contract.

## 3. Explicit `tach.toml` server dependency changes

server.py `depends_on` LOSES the three `code_checker_*` entries, GAINS `checker_tools` and `refactoring`.

## 4. Use existing `integration` marker instead of `refactoring_integration`

No new custom marker. Use `@pytest.mark.integration` which is already in pyproject.toml and CLAUDE.md convention. Excludable via `-m "not integration"`.

## 5. Late-binding dependency note for CheckerTools closures

The CheckerTools closures reference `self._server` attributes (like `_resolved_python`) at call time, not definition time. This late-binding is correct — no ordering issue — but closures capture the server reference, not its current attribute values.

## 6. Use `@pytest.mark.parametrize` for similar test cases

Steps 3 and 4 (jedi and rope tools) should use `@pytest.mark.parametrize` where multiple similar test cases exist (e.g., list_symbols for functions/classes/variables as one parameterized test).

## 7. Use `get_names()` for symbol position in find_references

In find_references, use `jedi.Script.get_names(all_scopes=False, definitions=True)` to find the symbol's line/column instead of manual source scanning.

## 8. Windows path handling

Use `Path` objects for all path operations. Rope and jedi may require forward-slash paths internally.

## 9. Register `integration` marker in pyproject.toml

Add `[tool.pytest.ini_options] markers = ["integration: ..."]` to prevent `PytestUnknownMarkWarning` and prepare for `--strict-markers`.

## 10. Verify import-linter pipe syntax after editing

The pipe-separated format (`module_a | module_b`) declares same-layer modules. Run `lint-imports` immediately after editing `.importlinter` to verify the syntax works with the installed version.

## 11. Defer server tach.toml dependency swap to Step 2

Step 1 only adds new module declarations (`checker_tools`, `refactoring`) without changing server's `depends_on`. The swap (removing `code_checker_*`, adding `checker_tools` + `refactoring`) happens in Step 2 when `checker_tools.py` exists. This ensures `tach_check` passes after each step.

## 12. Reorder server __init__ before CheckerTools registration

In Step 2, set `_resolved_python` and `_tool_availability` before calling `CheckerTools(self).register(self.mcp)`. Less fragile than relying on late-binding.

## 13. Catch all rope exceptions and convert to user-friendly strings

All rope exceptions (`BadIdentifierError`, `ModuleNotFoundError`, permission errors, etc.) must be caught in try/except blocks and returned as descriptive error strings. Never propagate raw rope exceptions to the MCP caller.

## 14. Flesh out test_move_symbol_name_collision

The test creates a destination file that already defines a symbol with the same name, calls `move_symbol`, and verifies a name collision error is returned.
