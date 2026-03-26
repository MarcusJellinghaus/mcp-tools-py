# Step 4: CLI wiring and vulture whitelist entry

> **Context**: See [summary.md](summary.md) for full architecture overview.

## LLM Prompt

```
Implement Step 4 of Issue #124 (see pr_info/steps/summary.md for context).

1. Add --vulture-whitelist CLI argument to main.py parse_args(), defaulting to
   "vulture_whitelist.py". Pass it through to create_server().

2. Add `_.run_vulture_check  # FastMCP tool handler` to vulture_whitelist.py
   (alongside existing tool handler entries).

Run all three code quality checks after editing. Fix any issues before committing.
```

## WHERE

- `src/mcp_tools_py/main.py`
- `vulture_whitelist.py`

## WHAT — Functions & Signatures

### main.py

**`parse_args()`** — add argument:
```python
parser.add_argument(
    "--vulture-whitelist",
    type=str,
    default="vulture_whitelist.py",
    help=(
        "Path to vulture whitelist file relative to project_dir. "
        "Auto-included when the file exists. Default: vulture_whitelist.py"
    ),
)
```

**`main()`** — pass to `create_server()`:
```python
server = create_server(
    project_dir,
    ...
    vulture_whitelist=args.vulture_whitelist,
)
```

### vulture_whitelist.py

Add one line in the "FastMCP decorators and handlers" section:
```python
_.run_vulture_check    # FastMCP tool handler
```

## HOW

1. In `parse_args()`, add the argument after `--refactoring-timeout`
2. In `main()`, add `vulture_whitelist=args.vulture_whitelist` to the `create_server()` call
3. In `vulture_whitelist.py`, add the entry after `_.run_lint_imports_check`

## DATA

- CLI arg: `--vulture-whitelist` → `args.vulture_whitelist: str`
- No new return types or data structures

## Commit

```
feat(main): expose --vulture-whitelist CLI arg and update whitelist

Part of #124. Wires vulture_whitelist param from CLI to server.
Adds run_vulture_check to the project's own vulture whitelist.
```
