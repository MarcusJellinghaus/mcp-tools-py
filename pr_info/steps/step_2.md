# Step 2: Migrate `checker_tools.py` and `formatter_tools.py` Consumers to `_is_tool_available()`

> **Context**: See `pr_info/steps/summary.md` for full issue context. Step 1 added `_is_tool_available()` to `ToolServer`.

## Goal

Switch all 8 availability checks in `checker_tools.py` and the 1 check in `formatter_tools.py` from dict access to the new method. Update the `test_checker_tools.py` and `test_formatter_tools.py` mock fixtures so existing tests pass.

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/checker_tools.py` | Modify |
| `tests/test_checker_tools.py` | Modify |
| `src/mcp_tools_py/formatter/formatter_tools.py` | Modify |
| `tests/test_formatter_tools.py` | Modify |

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

## WHAT — `formatter_tools.py` Changes

In `run_format_code`, replace:
```python
if not self._server._tool_availability.get(step, False):
```
with:
```python
if not self._server._is_tool_available(step):
```

This is inside the `for step in resolved_steps:` loop that checks each formatter step (black, isort) before running.

No other changes to `formatter_tools.py`.

## WHAT — `test_formatter_tools.py` Changes

### Update `mock_server` fixture

Add one line:
```python
server._is_tool_available = lambda tool: server._tool_availability.get(tool, False)
```

This preserves all existing test patterns, including `TestToolAvailability.test_tool_unavailable_returns_error` which sets `mock_server._tool_availability = {"isort": True, "black": False}`.

## DATA

No new data structures. The `_is_tool_available` method returns `bool`, same as the previous `.get(..., False)` pattern.

## HOW — Integration Points

- `checker_tools.py` and `formatter_tools.py` already hold `self._server` (a `ToolServer` reference). The method is called on that reference.
- No new imports in any file.

## LLM Prompt

```
Implement Step 2 of issue #158 (migrate checker_tools and formatter_tools consumers).
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

In formatter/formatter_tools.py:
Replace:
    if not self._server._tool_availability.get(step, False):
with:
    if not self._server._is_tool_available(step):

In test_formatter_tools.py:
Add one line to the mock_server fixture after the _tool_availability dict:
    server._is_tool_available = lambda tool: server._tool_availability.get(tool, False)

Run all three quality checks after changes. All must pass.
```
