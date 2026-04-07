# Plan Update Decisions

Decisions logged from the plan update discussion for issue #147.

## 2026-04-07

- **Include `docs/architecture/architecture.md` line 42 in Step 1.** The doc
  references `` `mcp[server]` `` (FastMCP) and must be updated to `` `mcp` ``
  to stay consistent with the `pyproject.toml` change. Both edits ship in a
  single commit. (Supervisor instruction.)
- **Update `Files Modified` table in `summary.md`** to list
  `docs/architecture/architecture.md` alongside `pyproject.toml`.
  (Supervisor instruction.)
- **Fix cosmetic acceptance-criteria checkboxes in `summary.md`** from `[x]`
  to `[ ]` since work has not started. (Supervisor instruction.)
- **Do NOT add a manual `pip install -e .` verification step.** Verification
  remains pylint/pytest/mypy via MCP tools only. (Supervisor instruction.)
