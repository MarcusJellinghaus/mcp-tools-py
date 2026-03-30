# Issue #10: Add `run_format_code` MCP tool + rename server

## Goal

Add a `run_format_code` MCP tool that formats project code using black and isort, and rename `CodeCheckerServer` → `ToolServer` to reflect the server's broader role.

## Architecture / Design Changes

### Server rename

- `CodeCheckerServer` → `ToolServer` (class in `server.py`)
- FastMCP service name: `"Code Checker Service"` → `"MCP Tools Service"`
- `create_server()` return type annotation updated; factory function signature unchanged

### New `formatter/` package

```
src/mcp_tools_py/formatter/
├── __init__.py            # Re-exports FormatterTools
├── formatter_tools.py     # FormatterTools class — registers run_format_code MCP tool
├── black_runner.py        # run_black() — calls python -m black, returns raw text
└── isort_runner.py        # run_isort() — calls python -m isort, returns raw text
```

Follows the same pattern as `CheckerTools`: a class that takes the server instance and registers tools via `register(mcp)`.

### New shared utility `utils/project_config.py`

Reads target directories from `pyproject.toml`:
- Source dirs from `[tool.setuptools.packages.find] where` (fallback: `["src"]` + warning)
- Test dirs from `[tool.pytest.ini_options] testpaths` (fallback: `["tests"]` + warning)
- Filters non-existent dirs silently; fails if none remain

### Dependency changes

- `black>=24.10.0` and `isort>=5.13.2` move from `[project.optional-dependencies] dev` to `[project] dependencies`

### Architecture layer changes (`tach.toml`)

- `mcp_tools_py.formatter` added to `tool_implementation` layer (depends on `utils`, `log_utils`)
- `mcp_tools_py.utils.project_config` added to `utilities` layer
- `mcp_tools_py.server` depends on `mcp_tools_py.formatter`

### Tool availability

- `black` and `isort` checked at startup via `python -m <tool> --version`, added to existing `_tool_availability` dict

## Files Created

| File | Purpose |
|------|---------|
| `src/mcp_tools_py/utils/project_config.py` | Shared pyproject.toml directory reader |
| `src/mcp_tools_py/formatter/__init__.py` | Package init, re-exports FormatterTools |
| `src/mcp_tools_py/formatter/formatter_tools.py` | MCP tool registration |
| `src/mcp_tools_py/formatter/black_runner.py` | Black subprocess runner |
| `src/mcp_tools_py/formatter/isort_runner.py` | Isort subprocess runner |
| `tests/test_project_config.py` | Tests for project_config utility |
| `tests/test_formatter_tools.py` | Tests for FormatterTools registration and logic |
| `tests/test_black_runner.py` | Tests for black runner |
| `tests/test_isort_runner.py` | Tests for isort runner |

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/server.py` | Rename class, service name, add formatter registration, add black/isort availability |
| `src/mcp_tools_py/checker_tools.py` | Update TYPE_CHECKING import (`CodeCheckerServer` → `ToolServer`) |
| `src/mcp_tools_py/utils/__init__.py` | Re-export `get_target_directories` and `TargetDirs` |
| `pyproject.toml` | Move black/isort to main deps |
| `tach.toml` | Add formatter module, project_config module, update server deps |
| `tests/test_tool_availability.py` | Update class name refs, add black/isort availability tests |
| `tests/test_checker_tools.py` | Update mock_server fixture for new availability keys |

## Implementation Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | `utils/project_config.py` — shared pyproject.toml reader + tests | 1 commit |
| 2 | `formatter/isort_runner.py` + `formatter/black_runner.py` — runner functions + tests | 1 commit |
| 3 | `formatter/formatter_tools.py` + `formatter/__init__.py` — MCP tool + tests | 1 commit |
| 4 | Server rename + wiring — rename class, move deps, availability checks, register FormatterTools, update tach.toml, update existing tests | 1 commit |
