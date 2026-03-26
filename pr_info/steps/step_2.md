# Step 2: Add `run_lint_imports_check` tool to `checker_tools.py` + tests

> **Context**: See `pr_info/steps/summary.md` for full issue context. Step 1 must be completed first (availability check in `server.py`).

## Goal

Register `run_lint_imports_check` as an MCP tool in `CheckerTools`, following the same pattern as pylint/pytest/mypy but simpler — raw text pass-through, no parsing.

## WHERE

- `src/mcp_tools_py/checker_tools.py` — add `_register_lint_imports()`, update `register()`
- `tests/test_checker_tools.py` — update registration count, add tool handler tests
- `tests/test_tool_availability.py` — add short-circuit test for lint-imports unavailability

## WHAT — Tests (write first)

### 1. Update registration count (`test_checker_tools.py`)

```python
def test_checker_tools_registers_three_tools(mock_server: MagicMock) -> None:
```
- Rename to `test_checker_tools_registers_four_tools`
- Change assertion: `assert mock_mcp.tool.call_count == 4`

### 2. Add success path test (`test_checker_tools.py`)

```python
def test_lint_imports_success_returns_raw_output(mock_server, checker_tools) -> None:
    """When lint-imports succeeds, return raw stdout."""
```
- Mock `execute_command` to return exit 0 with the success output text
- Call `run_lint_imports_check` via the registered tool
- Assert result contains "Contracts: 2 kept, 0 broken"

### 3. Add failure path test (`test_checker_tools.py`)

```python
def test_lint_imports_failure_returns_raw_output(mock_server, checker_tools) -> None:
    """When lint-imports fails, return raw stdout+stderr."""
```
- Mock `execute_command` to return exit 1 with "Could not read any configuration."
- Assert result contains "Could not read any configuration."

### 4. Add unavailability short-circuit test (`test_tool_availability.py`)

```python
def test_lint_imports_unavailable_returns_error(self) -> None:
    """When lint-imports is unavailable, tool handler returns error string."""
```
- Set `server._tool_availability["lint-imports"] = False`
- Call registered `run_lint_imports_check()`
- Assert "lint-imports is not available" in result

## WHAT — Implementation

### Method: `_register_lint_imports(self, mcp)` in `CheckerTools`

**Tool function signature:**
```python
@mcp.tool()
@log_function_call
def run_lint_imports_check(
    extra_args: Optional[List[str]] = None,
) -> str:
```

**Parameters:**
- `extra_args: Optional[List[str]]` — e.g. `["--contract", "layers"]`, `["--verbose"]`

**Returns:** `str` — raw lint-imports output (stdout + stderr combined)

### HOW — Integration

- Import `execute_command` (already imported in `checker_tools.py` indirectly via runners; add direct import from `mcp_tools_py.utils.subprocess_runner`)
- Add `import os` for platform detection and path joining
- Call from `register()`: `self._register_lint_imports(mcp)`

### ALGORITHM (pseudocode)

```
# Availability short-circuit
if not self._server._tool_availability.get("lint-imports", False):
    return "lint-imports is not available..."

# Resolve binary path
if os.name == "nt":
    binary = os.path.join(self._server.venv_path, "Scripts", "lint-imports")
else:
    binary = os.path.join(self._server.venv_path, "bin", "lint-imports")

# Build and execute command
command = [binary] + (extra_args or [])
result = execute_command(command, cwd=str(self._server.project_dir))

# Return raw output (stdout + stderr)
output = result.stdout
if result.stderr:
    output = output + "\n" + result.stderr if output else result.stderr
return output.strip() or "lint-imports produced no output."
```

### DATA — Return values

| Scenario | Return |
|----------|--------|
| Unavailable | `"lint-imports is not available in the configured Python environment..."` |
| Success (exit 0) | Raw stdout (e.g., "Contracts: 2 kept, 0 broken.") |
| Failure (exit 1) | Raw stdout+stderr (e.g., "Could not read any configuration.") |
| No output | `"lint-imports produced no output."` |
| Execution error | Raw error from `execute_command` result |

## Commit message

```
feat: add run_lint_imports_check MCP tool
```

## LLM Prompt

```
Implement Step 2 of issue #121 (see pr_info/steps/summary.md for context and pr_info/steps/step_2.md for details).

TDD approach: write tests first, then implement.

Key requirements:
- Add _register_lint_imports() to CheckerTools, call from register()
- Tool resolves lint-imports binary from venv_path (platform-aware)
- Uses execute_command() with cwd=project_dir
- Raw text pass-through for output (no parsing, no formatting layer)
- Optional extra_args parameter
- Update registration count test 3→4
- Add success, failure, and unavailability tests
- Run all three code quality checks (pylint, pytest, mypy) and fix any issues
```
