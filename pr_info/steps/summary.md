# Issue #158: Defer _check_tool_availability() to Speed Up MCP Server Startup

## Problem

`ToolServer.__init__` in `server.py` calls `_check_tool_availability()` which spawns 5 subprocesses in parallel (`pytest --version`, `pylint --version`, `mypy --version`, `black --version`, `isort --version`), each with a 10-second timeout. On Windows this takes 6-8 seconds, blocking the MCP handshake and causing Claude Code CLI to see `tools-py` as `"pending"` ~40% of the time.

## Solution

Split `_check_tool_availability()` into eager (fast) and lazy (slow) parts:

- **Eager** (stays in `__init__`): File-existence checks for lint-imports, vulture, ruff, bandit — these are <1ms and also set binary path attributes needed at runtime.
- **Lazy** (deferred to first invocation): The 5 subprocess checks (pytest, pylint, mypy, black, isort) move to a new `_is_tool_available(tool_name)` method that runs the subprocess on first call and caches the result.

## Architectural / Design Changes

### Before
```
__init__()
  └── _check_tool_availability()          # 6-8s blocking
        ├── ThreadPoolExecutor: 5 subprocess checks (pytest, pylint, mypy, black, isort)
        └── 4 file-existence checks (lint-imports, vulture, ruff, bandit)

Consumer access:  self._server._tool_availability.get("pylint", False)
```

### After
```
__init__()
  └── _check_tool_availability()          # <1ms, eager only
        └── 4 file-existence checks (lint-imports, vulture, ruff, bandit)

First tool invocation:
  └── _is_tool_available("pylint")        # ~1-2s one-time cost per tool
        ├── Cache hit → return immediately
        └── Cache miss → subprocess check → cache result → return

Consumer access:  self._server._is_tool_available("pylint")
```

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Single `_tool_availability` dict for both eager and lazy | `__init__` pre-populates with eager results; `_is_tool_available()` adds lazy results on cache miss. One dict, minimal change surface. |
| No thread safety | MCP tool calls are sequential from a single client |
| Log version string on lazy check | Free diagnostic info since we already run `--version` |
| Remove startup debug log | Per-tool logging at invocation time replaces it |

### Impact on Module Boundaries

No new modules or dependencies. Changes stay within the existing Server Layer → Tool Implementation Layer boundary. The `_is_tool_available()` method is a private API on `ToolServer`, consumed by `CheckerTools` and `FormatterTools` which already hold a reference to the server.

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/server.py` | Split `_check_tool_availability()`, add `_is_tool_available()`, remove debug log |
| `src/mcp_tools_py/checker_tools.py` | 8 sites: `.get("tool", False)` → `._is_tool_available("tool")` |
| `src/mcp_tools_py/formatter/formatter_tools.py` | 1 site: same consumer API change |
| `tests/test_tool_availability.py` | Rewrite for lazy behavior, add `_is_tool_available()` tests |
| `tests/test_checker_tools.py` | Add `_is_tool_available` lambda to mock fixture |
| `tests/test_formatter_tools.py` | Add `_is_tool_available` lambda to mock fixture |
| `tests/test_server_params.py` | Update patches for shrunk `_check_tool_availability` scope |

No files created. No files deleted.

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | `server.py`: Add `_is_tool_available()` method + shrink `_check_tool_availability()` + remove debug log. Update `test_tool_availability.py`. | Tests + implementation for core lazy mechanism |
| 2 | `checker_tools.py`: Switch 8 consumer sites to `_is_tool_available()`. Update `test_checker_tools.py` mock fixture. | Tests + consumer migration (checkers) |
| 3 | `formatter_tools.py`: Switch 1 consumer site to `_is_tool_available()`. Update `test_formatter_tools.py` mock fixture. | Tests + consumer migration (formatter) |
| 4 | `test_server_params.py`: Update patches for new `_check_tool_availability` scope. | Test-only fixes for integration tests |
