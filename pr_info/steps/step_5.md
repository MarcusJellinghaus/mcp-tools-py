# Step 5: Server + Checker Tools Integration

> **Context**: Read `pr_info/steps/summary.md` first for full architecture overview.

## Prompt

```
Implement Step 5 of Issue #149 (bandit security linter).
Read pr_info/steps/summary.md for architecture context, then read this step file.

Add bandit binary detection in server.py (same pattern as ruff/vulture binary checks)
and register the run_bandit_check MCP tool in checker_tools.py.

Follow the ruff/vulture binary check pattern in server.py and the ruff_check
registration pattern in checker_tools.py. Use format_bandit_report from reporting.py
to format the BanditResult into the final string.

After implementation, run all three code quality checks (pylint, pytest, mypy)
using MCP tools with the recommended fast unit test exclusions.
Commit: "feat(bandit): register run_bandit_check MCP tool"
```

## WHERE

- **Modify**: `src/mcp_tools_py/server.py` — add bandit binary check
- **Modify**: `src/mcp_tools_py/checker_tools.py` — add `_register_bandit()` method

## WHAT

### `server.py` — Binary Detection

Add bandit binary check block after the ruff block in `_check_tool_availability()`:

```python
# bandit: check via file existence (not subprocess)
bandit_available = False
bandit_binary: Optional[str] = None
if self.venv_path:
    if os.name == "nt":
        bandit_binary = os.path.join(self.venv_path, "Scripts", "bandit.exe")
    else:
        bandit_binary = os.path.join(self.venv_path, "bin", "bandit")
    bandit_available = os.path.exists(bandit_binary)
self._bandit_binary: Optional[str] = bandit_binary if bandit_available else None
availability["bandit"] = bandit_available
if not bandit_available:
    logger.warning(
        "bandit not found. Ensure --venv-path points to "
        "an environment where bandit is installed."
    )
```

### `checker_tools.py` — Registration

Add `_register_bandit()` method and call it from `register()`.

```python
def _register_bandit(self, mcp: "FastMCPProtocol") -> None:
    """Register the bandit security checker tool."""

    @mcp.tool()
    @log_function_call
    def run_bandit_check(
        target_directories: Optional[List[str]] = None,
        extra_args: Optional[List[str]] = None,
        max_issues: int = 1,
    ) -> str:
        """Run bandit security linter on the project code.

        Args:
            target_directories: Directories to analyze relative to project_dir.
                Auto-detected from pyproject.toml when None.
            extra_args: Additional bandit CLI flags.
            max_issues: Number of issue types to show in detail (default: 1).
                Remaining issues shown as summary counts.
        """
```

### ALGORITHM — `run_bandit_check` (inside registration)

```
1. Check availability → return not-available message if False
2. Resolve target_directories via resolve_target_directories()
3. Call run_bandit_check_impl(binary, project_dir, resolved, extra_args)
4. If result.error → return error string
5. Call format_bandit_report(result.messages, result.errors, max_issues)
6. Return formatted report or "No bandit security issues found."
```

### DATA

**Imports to add to `checker_tools.py`**:
```python
from mcp_tools_py.code_checker_bandit.runners import run_bandit_check_impl
from mcp_tools_py.code_checker_bandit.reporting import format_bandit_report
```

**Call added to `register()`**:
```python
self._register_bandit(mcp)
```

## HOW

- Follow exact same structure as `_register_ruff_check` in checker_tools.py
- Binary check follows vulture/ruff pattern in server.py — file existence, not subprocess
- Use `resolve_target_directories()` for auto-detection (already imported)
- No new test file needed — existing `test_tool_availability.py` and `test_checker_tools.py` patterns cover integration; the unit logic is already tested in steps 2-4

## Notes

- The `_register_bandit` method is intentionally simpler than pylint/mypy registration because:
  - No `get_bandit_prompt()` convenience function (runner + reporting are called separately)
  - No special formatting method on CheckerTools (report formatting lives in reporting.py)
  - Error handling follows the ruff pattern (check result.error, then format)
