# Step 1: Create UtilityTools class with sleep tool + tests (TDD)

> **Context**: See [summary.md](summary.md) for full issue context.

## Commit message
`feat: add sleep MCP tool via UtilityTools class`

## WHERE

| Action | File |
|--------|------|
| Create | `src/mcp_tools_py/utility_tools.py` |
| Create | `tests/test_utility_tools.py` |

## WHAT

### `src/mcp_tools_py/utility_tools.py`

```python
class UtilityTools:
    def register(self, mcp: "FastMCPProtocol") -> None: ...
    # Registers one tool: sleep(sleep_seconds: float = 5.0) -> str
```

**Tool function signature:**
```python
def sleep(sleep_seconds: float = 5.0) -> str:
    """Pause execution for the specified number of seconds.

    Args:
        sleep_seconds: Duration to sleep in seconds (0-300, default: 5.0).
    """
```

### `tests/test_utility_tools.py`

Test functions:
- `test_utility_tools_registers_sleep_tool()` — mock mcp, verify `sleep` tool is registered
- `test_sleep_valid_values(sleep_seconds, expected_message)` — parameterized: (default 5.0), (10.0), (0) — mock `time.sleep`, verify correct sleep call and return message
- `test_sleep_invalid_values(sleep_seconds, expected_error)` — parameterized: (-1, error), (301, error) — verify error returned, `time.sleep` NOT called

## HOW

### Integration points
- Import `log_function_call` from `mcp_tools_py.log_utils`
- Import `FastMCPProtocol` under `TYPE_CHECKING` from `mcp_tools_py.server`
- Decorators: `@mcp.tool()` then `@log_function_call` (same order as existing tools)

### ALGORITHM (core logic)

```
def sleep(sleep_seconds: float = 5.0) -> str:
    if sleep_seconds < 0:
        return "Error: sleep_seconds must be >= 0."
    if sleep_seconds > 300:
        return "Error: sleep_seconds must be <= 300."
    time.sleep(sleep_seconds)
    return f"Slept for {sleep_seconds} seconds."
```

## DATA

- **Input**: `sleep_seconds: float` (default 5.0)
- **Output**: `str` — either `"Slept for X seconds."` or `"Error: ..."`
- **No models, no data classes** — just a string return

## LLM Prompt

```
Implement Step 1 of issue #116 (see pr_info/steps/summary.md for context).

Create two files using TDD:

1. First write tests in `tests/test_utility_tools.py` — see step_1.md for the 3 test cases (2 are parameterized).
   Mock `time.sleep` to avoid actual delays. Mock `mcp.tool()` for registration test.

2. Then implement `src/mcp_tools_py/utility_tools.py`:
   - UtilityTools class following the same `register(mcp)` pattern as existing tool classes
   - Single `sleep` tool: validates 0 <= sleep_seconds <= 300, calls time.sleep(), returns confirmation
   - Use @mcp.tool() and @log_function_call decorators

3. Run all three code quality checks (pylint, mypy, pytest) and fix any issues.

4. Commit with message: "feat: add sleep MCP tool via UtilityTools class"
```
