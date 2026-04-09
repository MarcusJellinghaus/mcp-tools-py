# Step 5: Architecture Config + Dependency

> **Context**: See `pr_info/steps/summary.md` for the full plan. This is step 5 of 5.

## Goal

Add `ruff>=0.9.0` to dependencies and update architecture enforcement configs (`tach.toml`, `.importlinter`) so the new module passes all boundary checks.

## LLM Prompt

```
Read pr_info/steps/summary.md for full context, then implement step 5.

Add ruff>=0.9.0 to pyproject.toml dependencies. Update tach.toml to declare
code_checker_ruff as a tool_implementation module (depends on utils + log_utils)
and add it to checker_tools depends_on. Update .importlinter to add
code_checker_ruff to the layers contract (same tier as other checkers) and
the forbidden-imports forbidden_modules list for utils.

After implementation, run all three code quality checks (pylint, pytest, mypy).
Also run lint-imports check if possible. Fix any issues before committing.
```

## WHERE

**Modify:**
- `pyproject.toml`
- `tach.toml`
- `.importlinter`

## WHAT

### `pyproject.toml`

Add to `dependencies` list:
```toml
"ruff>=0.9.0",
```

### `tach.toml`

Add new module block (after `code_checker_vulture`):
```toml
[[modules]]
path = "mcp_tools_py.code_checker_ruff"
layer = "tool_implementation"
depends_on = [
    { path = "mcp_tools_py.utils" },
    { path = "mcp_tools_py.log_utils" }
]
```

Update `checker_tools` module's `depends_on` — add:
```toml
{ path = "mcp_tools_py.code_checker_ruff" },
```

### `.importlinter`

Update layers contract — add `mcp_tools_py.code_checker_ruff` to the checker tier:
```ini
    mcp_tools_py.code_checker_pytest | mcp_tools_py.code_checker_pylint | mcp_tools_py.code_checker_mypy | mcp_tools_py.code_checker_ruff
```

Update forbidden-imports contract — add to `forbidden_modules`:
```ini
    mcp_tools_py.code_checker_ruff
```

## HOW

These are pure config file edits. No code changes. The architecture tools (tach, import-linter) use these configs to enforce module boundaries at CI time.

## DATA

No new data structures. Config-only step.

## Verification

After edits, verify:
1. `pylint` passes (no new code, just config)
2. `pytest` passes (all existing + new tests)
3. `mypy` passes (no new code, just config)
4. `lint-imports` passes if available (validates .importlinter config)

## Commit

```
feat(ruff): add ruff dependency and architecture enforcement config

- Add ruff>=0.9.0 to pyproject.toml dependencies
- Declare code_checker_ruff module in tach.toml (tool_implementation layer)
- Add code_checker_ruff to checker_tools depends_on in tach.toml
- Update .importlinter layers and forbidden-imports contracts
```
