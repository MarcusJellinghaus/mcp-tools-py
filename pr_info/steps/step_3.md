# Step 3: Migrate `formatter_tools.py` Consumer to `_is_tool_available()`

> **Context**: See `pr_info/steps/summary.md` for context. Step 1 added the method, Step 2 migrated checkers.

## Goal

Switch the 1 availability check in `formatter_tools.py` from dict access to `_is_tool_available()`. Update the `test_formatter_tools.py` mock fixture.

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/formatter/formatter_tools.py` | Modify |
| `tests/test_formatter_tools.py` | Modify |

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

No new data structures. Same `bool` return as before.

## HOW — Integration Points

- `formatter_tools.py` already holds `self._server`. Method called on that reference.
- No new imports.

## LLM Prompt

```
Implement Step 3 of issue #158 (migrate formatter_tools consumer).
See pr_info/steps/summary.md for context and pr_info/steps/step_3.md for detailed spec.

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
