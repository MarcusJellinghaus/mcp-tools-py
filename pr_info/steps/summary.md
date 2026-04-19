# Summary: Migrate .mcp.json to new KV format and add permissions (#172)

## Overview

Config-only change — no Python code, no tests, no architectural changes.

Two config files are updated to support the new mcp-workspace `--reference-project` KV format and add permissions for the obsidian-wiki MCP server.

## Design / Architectural Changes

**None.** This issue modifies only configuration files. No source code, tests, or project architecture is affected.

## Files Modified

| File | Change |
|------|--------|
| `.mcp.json` | Migrate 4 `--reference-project` args from `name=path` to `name=X,path=Y,url=Z` format; rename `p_coder_utils` → `p_coder-utils` |
| `.claude/settings.local.json` | Add 11 `mcp__obsidian-wiki__*` permissions; add `mcp__workspace__search_reference_files` permission |

## Files Created

None.

## Steps

| Step | Description | Commit |
|------|-------------|--------|
| 1 | Migrate `.mcp.json` reference-project args to new KV format | config-only |
| 2 | Add obsidian-wiki and search_reference_files permissions to settings | config-only |

## Constraints

- No code quality checks required (no Python changes)
- Windows backslash escaping (`\\`) must be preserved in `.mcp.json`
- TDD does not apply (no testable logic)
