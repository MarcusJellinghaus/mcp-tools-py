# Step 2: Migrate `checker_tools.py` Consumers to `_is_tool_available()`

> **Context**: See `pr_info/steps/summary.md` for full issue context. Step 1 added `_is_tool_available()` to `ToolServer`.

## Goal

Switch all 8 availability checks in `checker_tools.py` from dict access to the new method. Update the `test_checker_tools.py` mock fixture so existing tests pass.

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/checker_tools.py` | Modify |
| `tests/test_checker_tools.py` | Modify |

## WHAT — `checker_tools.py` Changes

Replace 8 occurrences of:
```python
self._server._tool_availability.get("tool_name", False)
```
with:
```python
self._server._is_tool_available("tool_name")
```

### Exact sites (line references are approximate):

1. `run_pylint_check` — `"pylint"`
2. `run_pytest_check` — `"pytest"`
3. `run_mypy_check` — `"mypy"`
4. `run_lint_imports_check` — `"lint-imports"`
5. `run_vulture_check` — `"vulture"`
6. `run_ruff_check` — `"ruff"`
7. `run_ruff_fix` — `"ruff"`
8. `run_bandit_check` — `"bandit"`

No other changes to `checker_tools.py`.

## WHAT — `test_checker_tools.py` Changes

### Update `mock_server` fixture

Add one line to provide `_is_tool_available` on the mock, delegating to the existing dict:

```python
server._is_tool_available = lambda tool: server._tool_availability.get(tool, False)
```

This preserves all existing test patterns:
- Tests that check `mock_server._tool_availability["ruff"] = False` continue to work.
- Tests that use the full dict with all tools `True` continue to work.
- No individual test methods need changes.

## DATA

No new data structures. The `_is_tool_available` method returns `bool`, same as the previous `.get(..., False)` pattern.

## HOW — Integration Points

- `checker_tools.py` already holds `self._server` (a `ToolServer` reference). The method is called on that reference.
- No new imports in either file.

## LLM Prompt

```
Implement Step 2 of issue #158 (migrate checker_tools consumers).
See pr_info/steps/summary.md for context and pr_info/steps/step_2.md for detailed spec.

In checker_tools.py:
Replace all 8 occurrences of:
    self._server._tool_availability.get("TOOL", False)
with:
    self._server._is_tool_available("TOOL")

The 8 tools are: pylint, pytest, mypy, lint-imports, vulture, ruff (2 sites), bandit.

In test_checker_tools.py:
Add one line to the mock_server fixture after the _tool_availability dict is set:
    server._is_tool_available = lambda tool: server._tool_availability.get(tool, False)

Run all three quality checks after changes. All must pass.
```
