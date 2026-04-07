# Step 1: Remove `mcp[server]` extra from pyproject.toml

**Commit message:** `fix: remove obsolete mcp[server] extra from dependencies (#147)`

## Context

See [summary.md](summary.md) for full context. This is the only step.

## WHERE

- `pyproject.toml` — the `[project] dependencies` list

## WHAT

Remove the line:
```toml
"mcp[server]>=1.3.0",
```

Keep these lines unchanged:
```toml
"mcp>=1.3.0",
"mcp[cli]>=1.3.0",
```

## HOW

Single edit operation removing one line from the dependencies array.

## DATA

No code changes. No new functions, signatures, or data structures.

## Verification

1. Run pylint, pytest (unit tests), and mypy — all must pass
2. Confirm `"mcp>=1.3.0"` and `"mcp[cli]>=1.3.0"` are still present
3. Confirm `"mcp[server]>=1.3.0"` is gone

## TDD Note

No test needed — this is a packaging metadata change with no runtime behavior change. The existing test suite serves as the regression check.

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_1.md.

In pyproject.toml, remove the line `"mcp[server]>=1.3.0",` from the
`[project] dependencies` list. Keep `"mcp>=1.3.0"` and `"mcp[cli]>=1.3.0"`
unchanged.

Run all code quality checks (pylint, pytest, mypy) to confirm nothing breaks.
Format and commit with message: fix: remove obsolete mcp[server] extra from dependencies (#147)
```
