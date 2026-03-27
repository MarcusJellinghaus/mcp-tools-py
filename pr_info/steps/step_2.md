# Step 2: Register run_vulture_check tool in checker_tools.py

> **Context**: See [summary.md](summary.md) for full architecture overview.

## LLM Prompt

```
Implement Step 2 of Issue #124 (see pr_info/steps/summary.md for context).

Add _register_vulture() to CheckerTools in checker_tools.py, following the
lint-imports pattern exactly. The tool returns raw output — no formatter method.

Update tests in tests/test_checker_tools.py:
- Update mock_server fixture: add "vulture": True to _tool_availability, add _vulture_binary
- Update registration count test from 4 to 5
- Add tests: vulture unavailable message, successful execution, whitelist auto-detection

Read the lint-imports registration (_register_lint_imports) and its tests
(test_lint_imports_success_returns_raw_output, test_lint_imports_failure_returns_raw_output)
as the pattern to follow.

Run all three code quality checks after editing. Fix any issues before committing.
```

## WHERE

- `src/mcp_tools_py/checker_tools.py`
- `tests/test_checker_tools.py`

## WHAT — Functions & Signatures

### checker_tools.py

**`_register_vulture(self, mcp: "FastMCPProtocol") -> None`** — new method

Inner tool function signature:
```python
def run_vulture_check(
    target_directories: Optional[List[str]] = None,
    min_confidence: int = 60,
    extra_args: Optional[List[str]] = None,
) -> str:
```

**`register(self, mcp)`** — add `self._register_vulture(mcp)` call.

**Class docstring** — update to mention vulture.

## HOW — Integration Points

1. `@mcp.tool()` and `@log_function_call` decorators (same as lint-imports)
2. Add `import os` — needed for `os.path.isdir()` (tests dir check). `execute_command` is already imported.
3. Access `self._server._vulture_binary`, `self._server.project_dir`, `self._server.vulture_whitelist`

## ALGORITHM — run_vulture_check core logic

```
if not self._server._tool_availability.get("vulture", False):
    return unavailable message with binary path

binary = self._server._vulture_binary
dirs = target_directories or ["src"] + (["tests"] if tests_dir_exists else [])
command = [binary] + dirs + ["--min-confidence", str(min_confidence)]

whitelist_path = project_dir / self._server.vulture_whitelist
if whitelist_path.exists():
    command.append(str(whitelist_path))

command += (extra_args or [])
result = execute_command(command, cwd=str(project_dir))
return combined stdout+stderr or "no output" fallback
```

## DATA

- **Input**: `target_directories: Optional[List[str]]`, `min_confidence: int`, `extra_args: Optional[List[str]]`
- **Output**: `str` — raw vulture CLI output (stdout + stderr combined)

## Tests to add in test_checker_tools.py

### Fixture updates
- `mock_server`: add `"vulture": True` to `_tool_availability`, add `_vulture_binary = "/mock/venv/bin/vulture"`
- `mock_server`: add `vulture_whitelist = "vulture_whitelist.py"` (`project_dir` already exists in fixture)

### New tests (follow lint-imports test pattern with `capture` helper)
1. **`test_checker_tools_registers_five_tools`** — update existing test, assert `mock_mcp.tool.call_count == 5`
2. **`test_vulture_unavailable_returns_error`** — set `"vulture": False`, call tool, assert "vulture is not available" in result
3. **`test_vulture_success_returns_raw_output`** — mock `execute_command` returning stdout, assert output returned
4. **`test_vulture_failure_returns_raw_output`** — mock `execute_command` returning stderr, assert stderr in output
5. **`test_vulture_whitelist_auto_included`** — mock `Path.exists` to return True for whitelist, assert whitelist path in command args
6. **`test_vulture_default_directories`** — verify default dirs are `["src"]` (+ `"tests"` if exists)

## Commit

```
feat(checker_tools): add run_vulture_check MCP tool

Part of #124. Registers vulture dead-code detection tool following the
lint-imports pattern: binary lookup, execute_command, raw output.
```
