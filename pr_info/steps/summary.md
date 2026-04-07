# Summary: Remove obsolete `mcp[server]` extra from dependencies

**Issue:** #147  
**Type:** Bug fix (dependency warning removal)

## Problem

Installing the package emits:
```
warning: The package `mcp==1.27.0` does not have an extra named `server`
```

The `mcp[server]` extra no longer exists in modern `mcp` releases. The plain `mcp` package already provides everything needed (`mcp.server.fastmcp`).

## Architectural / Design Changes

**None.** This is a metadata-only change to `pyproject.toml`. No code, no architecture, no runtime behavior changes. The `mcp[server]` line was already redundant since `mcp>=1.3.0` (without extras) provides the same modules.

## Fix

Remove the single line `"mcp[server]>=1.3.0",` from `pyproject.toml` dependencies.

## Files Modified

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | **Modified** | Remove `"mcp[server]>=1.3.0"` from `[project] dependencies` |

No files created. No files deleted.

## Acceptance Criteria

- [x] `"mcp[server]>=1.3.0"` line removed from `pyproject.toml`
- [x] `"mcp>=1.3.0"` and `"mcp[cli]>=1.3.0"` remain unchanged
- [x] All code quality checks pass (pylint, pytest, mypy)
