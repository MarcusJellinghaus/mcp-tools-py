# Step 4: Add import-linter isolation contract

**Summary:** [summary.md](./summary.md)

## Goal

Add a `forbidden` contract to `.importlinter` that prevents any module except the three shim files from importing `mcp_coder_utils` directly. This enforces the shim pattern at CI time.

## Test first

No new test file — verification is done by running `lint-imports` itself (`mcp__tools-py__run_lint_imports_check`). The contract IS the test.

Optional: a quick smoke test that intentionally confirms the contract exists:

### WHERE
`tests/test_shim_reexports.py` (append)

### WHAT
```python
def test_importlinter_config_has_isolation_contract():
    """Verify the isolation contract is defined in .importlinter."""
    config = Path(".importlinter").read_text()
    assert "mcp_coder_utils_isolation" in config
```

## Implementation

### WHERE
`.importlinter`

### WHAT
Append a new contract section:

```ini
[importlinter:contract:mcp_coder_utils_isolation]
name = mcp_coder_utils imports only via shims
type = forbidden
source_modules =
    mcp_tools_py
forbidden_modules =
    mcp_coder_utils
ignore_imports =
    mcp_tools_py.utils.subprocess_runner -> mcp_coder_utils
    mcp_tools_py.utils.file_utils -> mcp_coder_utils
    mcp_tools_py.log_utils -> mcp_coder_utils
```

### HOW
- `type = forbidden` — same contract type already used in the file for `forbidden-imports`.
- `source_modules = mcp_tools_py` — covers the entire package.
- `forbidden_modules = mcp_coder_utils` — the external package.
- `ignore_imports` — whitelists the 3 shim files that are allowed to import directly.

### ALGORITHM
```
1. Append the new contract block to .importlinter
2. Run lint-imports to verify it passes
3. If any violations found, a direct import was missed in steps 2-3 — fix it
```

### DATA
No code data structures. The contract is configuration only.

## Verify

Run lint-imports, pylint, pytest, mypy — all must pass.

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_4.md.
Implement step 4: add the mcp_coder_utils_isolation forbidden contract to .importlinter.
Add the smoke test. Run lint-imports first to verify isolation, then all code quality checks.
```
