# Step 4: Update `test_server_params.py` Patches

> **Context**: See `pr_info/steps/summary.md` for context. Steps 1-3 completed the production code changes.

## Goal

Fix `test_server_params.py` which patches `_check_tool_availability` in 4 places. After step 1, `_check_tool_availability` only returns eager tools (lint-imports, vulture, ruff, bandit), but these tests patch it to return `{"pytest": True, "pylint": True, "mypy": True}` and then call tool handlers that now use `_is_tool_available()`.

## WHERE

| File | Action |
|------|--------|
| `tests/test_server_params.py` | Modify |

## WHAT — Changes

### Strategy

The 4 `patch.object(ToolServer, "_check_tool_availability", ...)` calls need updating. The simplest fix: **keep the patches** (they still prevent real file-existence checks at init), but also **mock `_is_tool_available`** on the server instance after creation so tool handlers don't trigger real subprocesses.

### Specific changes

1. **`mock_server` fixture** and **`test_mcp_tool_decorator_compatibility`**: Both use `patch.object(ToolServer, "_check_tool_availability", return_value={...})`. Update the return value to only contain eager tools (or empty dict). After server creation, add:
   ```python
   server._is_tool_available = lambda tool: True
   ```

2. **`test_run_pytest_check_parameters`**, **`test_run_pylint_check_signature`**: Same pattern — update patched return value and add `_is_tool_available` override on the server instance.

3. **`TestServerPylintMaxIssues`** tests: These create `ToolServer` without patching `_check_tool_availability` at all (they rely on mocked `execute_command`). After step 1, `_check_tool_availability` no longer calls `execute_command`, so these may need `_is_tool_available` mocked if their tool handlers call it. Check each test and add the lambda where needed.

### Pattern for each test

```python
# Before (current):
with patch.object(
    ToolServer,
    "_check_tool_availability",
    return_value={"pytest": True, "pylint": True, "mypy": True},
):
    server = ToolServer(project_dir=Path("/test/project"))

# After:
with patch.object(
    ToolServer,
    "_check_tool_availability",
    return_value={},
):
    server = ToolServer(project_dir=Path("/test/project"))
    server._is_tool_available = lambda tool: True
```

## DATA

No new data structures. This is a test-only change.

## HOW — Integration Points

- No production code changes in this step.
- Tests already import `ToolServer` from `mcp_tools_py.server`.

## LLM Prompt

```
Implement Step 4 of issue #158 (fix test_server_params.py).
See pr_info/steps/summary.md for context and pr_info/steps/step_4.md for detailed spec.

In test_server_params.py:
1. Find all 4 places that patch _check_tool_availability with return values
   containing subprocess tools (pytest, pylint, mypy). Update return values
   to empty dict or eager-only tools.
2. After each server creation, add:
       server._is_tool_available = lambda tool: True
   (or assign to _server if that's the variable name).
3. For TestServerPylintMaxIssues tests that create ToolServer without patching
   _check_tool_availability: add _is_tool_available override after server creation.
4. Verify the _get_tool helper and all assertions still work.

Run all three quality checks after changes. All must pass.
```
