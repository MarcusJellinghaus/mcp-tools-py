# Step 4: Server Discovery + Checker Tools Registration

> **Context**: See `pr_info/steps/summary.md` for the full plan. This is step 4 of 5.

## Goal

Wire ruff into the MCP server: add binary discovery in `server.py` and register `run_ruff_check` + `run_ruff_fix` as MCP tools in `checker_tools.py`.

## LLM Prompt

```
Read pr_info/steps/summary.md for full context, then implement step 4.

Add ruff binary discovery in server.py (same pattern as vulture/lint-imports:
binary-in-venv file existence check). Then add _register_ruff_check() and
_register_ruff_fix() in checker_tools.py following the vulture registration pattern.

Update tests/test_checker_tools.py: update tool count assertion from 5→7,
add "ruff" to mock_server fixture's _tool_availability dict and _ruff_binary.

After implementation, run all three code quality checks (pylint, pytest, mypy).
Fix any issues before committing.
```

## WHERE

**Modify:**
- `src/mcp_tools_py/server.py` — add ruff discovery in `_check_tool_availability()`
- `src/mcp_tools_py/checker_tools.py` — add imports + `_register_ruff_check()` + `_register_ruff_fix()`
- `tests/test_checker_tools.py` — update mock fixtures and tool count assertion

## WHAT

### `server.py` changes

In `_check_tool_availability()`, after the vulture block, add:

```python
# ruff: check via file existence (not subprocess)
ruff_available = False
ruff_binary: Optional[str] = None
if self.venv_path:
    if os.name == "nt":
        ruff_binary = os.path.join(self.venv_path, "Scripts", "ruff.exe")
    else:
        ruff_binary = os.path.join(self.venv_path, "bin", "ruff")
    ruff_available = os.path.exists(ruff_binary)
self._ruff_binary: Optional[str] = ruff_binary if ruff_available else None
availability["ruff"] = ruff_available
if not ruff_available:
    logger.warning(
        "ruff not found. Ensure --venv-path points to "
        "an environment where ruff is installed."
    )
```

### `checker_tools.py` changes

Add to imports:
```python
from mcp_tools_py.code_checker_ruff.runners import run_ruff_check_impl, run_ruff_fix_impl
```

Add to `register()`:
```python
self._register_ruff_check(mcp)
self._register_ruff_fix(mcp)
```

New methods — `_register_ruff_check(mcp)` and `_register_ruff_fix(mcp)`:

```python
def _register_ruff_check(self, mcp: "FastMCPProtocol") -> None:
    @mcp.tool()
    @log_function_call
    def run_ruff_check(
        select: Optional[List[str]] = None,
        target_directories: Optional[List[str]] = None,
        extra_args: Optional[List[str]] = None,
        max_issues: int = 1,
    ) -> str:
        """Run ruff check on the project (read-only analysis).
        
        Args:
            select: Override rule selection (e.g. ["D", "DOC"]). Defaults to project config.
            target_directories: Directories to check relative to project_dir. Auto-detected when None.
            extra_args: Additional ruff CLI flags (e.g. ["--preview"] for DOC rules).
            max_issues: Number of issue types shown in detail (default: 1).
        """
        # availability guard → resolve target dirs → call run_ruff_check_impl

def _register_ruff_fix(self, mcp: "FastMCPProtocol") -> None:
    @mcp.tool()
    @log_function_call
    def run_ruff_fix(
        select: Optional[List[str]] = None,
        target_directories: Optional[List[str]] = None,
        extra_args: Optional[List[str]] = None,
    ) -> str:
        """Run ruff check --fix on the project (MODIFIES FILES in-place).
        
        Only applies safe fixes by default. Pass ["--unsafe-fixes"] via
        extra_args to also apply unsafe fixes.
        
        Args:
            select: Override rule selection. Defaults to project config.
            target_directories: Directories to fix relative to project_dir. Auto-detected when None.
            extra_args: Additional ruff CLI flags.
        """
        # availability guard → resolve target dirs → call run_ruff_fix_impl
```

## HOW

Both tool registrations follow the exact same pattern as `_register_vulture`:
1. Check `self._server._tool_availability.get("ruff", False)` → return unavailable message
2. `resolve_target_directories(project_dir, target_directories)` → return error if string
3. Call runner function with `self._server._ruff_binary`
4. Wrap in try/except with structured logging

## DATA

Tool parameters match issue requirements:
- `run_ruff_check`: `select`, `target_directories`, `extra_args`, `max_issues`
- `run_ruff_fix`: `select`, `target_directories`, `extra_args` (no `max_issues`)

## Tests — `test_checker_tools.py` changes

1. Update `mock_server` fixture: add `"ruff": True` to `_tool_availability`, add `server._ruff_binary = "/mock/venv/bin/ruff"`
2. Update `test_checker_tools_registers_five_tools` → rename to `test_checker_tools_registers_seven_tools`, assert `mock_mcp.tool.call_count == 7`

## Commit

```
feat(ruff): wire ruff tools into MCP server

- Add ruff binary-in-venv discovery in server._check_tool_availability()
- Register run_ruff_check and run_ruff_fix MCP tools in CheckerTools
- Both tools follow established availability-guard + logging pattern
- Update test fixture and tool count assertion (5→7)
```
