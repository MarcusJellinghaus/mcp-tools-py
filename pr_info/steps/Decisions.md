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
