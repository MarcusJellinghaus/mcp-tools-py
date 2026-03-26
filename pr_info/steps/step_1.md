# Step 1: Move vulture and import-linter to core dependencies

> **Context**: See [summary.md](summary.md) for full architecture overview.

## LLM Prompt

```
Implement Step 1 of Issue #124 (see pr_info/steps/summary.md for context).

Move `vulture>=2.13` and `import-linter>=2.0` from `[project.optional-dependencies] dev`
to `[project] dependencies` in pyproject.toml. Remove them from the dev list.
No other changes. Run all three code quality checks after editing.
```

## WHERE

- `pyproject.toml`

## WHAT

Move two dependency lines between sections. No new functions or signatures.

## HOW

Edit `pyproject.toml` only:
1. Add `"vulture>=2.13"` and `"import-linter>=2.0"` to the `dependencies` list
2. Remove both from the `[project.optional-dependencies] dev` list

## DATA

No code changes — config-only.

## Commit

```
feat(deps): move vulture and import-linter to core dependencies

Part of #124. Both tools are now required at runtime for MCP tool
registration, not just development.
```
