# Summary: Remove redundant bare `mcp` dependency (#204)

## Goal

`pyproject.toml` lists `mcp` twice. `mcp[cli]` already installs everything the bare
`mcp` requirement does, so remove the bare line and record why the cap exists.

## Architectural / design changes

None. No source module, public API, import contract or tool registration changes.
The resolved dependency set is unchanged, so the server behaves as before.

Project decisions that stay as they are:

- The `[cli]` extra stays: the README documents `mcp dev`.
- The `<2.0.0` cap and the mypy override for `mcp.server.fastmcp` stay until #216.
- No pinning: `uv.lock` stays gitignored, and no lockfile or constraints file is added.
- The CI install steps do not change.

## Files

### Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Replace the bare `mcp` requirement with a comment explaining the cap |
| `docs/architecture/architecture.md` | Remove bare `mcp` from the runtime dependency list (line 48) |

### Created

No permanent files. `.scratch/` holds one-off probes during the step and is deleted
before the commit, because CI blocks any PR that contains it.

No folders or modules are created.

## Testing approach

The issue rules out a new permanent test, because the resolved dependency set does not
change. The test-first order is kept through a scratch probe:

1. Capture the `uv pip compile` output before the edit.
2. Make the edit.
3. Compare the output after the edit, and check the requirement and the tool list.

## Out of scope

- The SDK v2 migration (#216)
- The out-of-date `mcp dev src/server.py` path at `README.md:510`

## Steps

- [Step 1](./step_1.md): remove the bare `mcp` requirement and verify the resolve is unchanged
