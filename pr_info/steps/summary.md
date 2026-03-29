# Issue #128: Add `[tool.mcp-coder.from-github]` config to pyproject.toml

## Summary

Add a `[tool.mcp-coder.from-github]` configuration section to `pyproject.toml` so that `mcp-coder vscodeclaude launch --from-github` knows which sibling packages to install from GitHub source for this project.

## Architectural / Design Changes

**None.** This is a declarative, config-only change. No code, no tests, no new modules. It adds metadata consumed by an external tool (`mcp-coder`) — the project's runtime behavior is unaffected.

The new section declares:
- **`packages`** — sibling packages installed *with* dependencies (`mcp-config-tool`, `mcp-workspace`)
- **`packages-no-deps`** — sibling packages installed *without* dependencies to avoid version conflicts (`mcp-coder`)

`mcp-tools-py` (this project) is intentionally omitted — it is handled automatically by `--from-github`.

## Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Insert `[tool.mcp-coder.from-github]` section after `[tool.pylint.messages_control]`, before `[tool.setuptools]` |

No files created. No files deleted.

## Implementation Steps

| Step | Description |
|------|-------------|
| [Step 1](step_1.md) | Add `[tool.mcp-coder.from-github]` section to `pyproject.toml` |
