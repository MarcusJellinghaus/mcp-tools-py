# Step 4: Update `.importlinter` (Add tach + vulture to Contracts)

## LLM Prompt
> Read `pr_info/steps/summary.md` and `pr_info/steps/step_4.md`, then implement step 4. Update `.importlinter` to add both `mcp_tools_py.code_checker_tach` AND `mcp_tools_py.code_checker_vulture` to the layers contract and the forbidden-imports contract. Run `mcp__tools-py__run_lint_imports_check`, `run_pylint_check`, `run_pytest_check`, `run_mypy_check`; all must pass before commit.

## WHERE

Modify:
- `.importlinter`

## WHAT

### Layers contract

In `[importlinter:contract:layers]`, on the line listing the checker modules, add `code_checker_vulture` and `code_checker_tach`:

```ini
mcp_tools_py.code_checker_pytest | mcp_tools_py.code_checker_pylint | mcp_tools_py.code_checker_mypy | mcp_tools_py.code_checker_ruff | mcp_tools_py.code_checker_bandit | mcp_tools_py.code_checker_vulture | mcp_tools_py.code_checker_tach
```

### Forbidden-imports contract

In `[importlinter:contract:forbidden-imports]` (`source_modules = mcp_tools_py.utils`), add to `forbidden_modules`:

```ini
mcp_tools_py.code_checker_vulture
mcp_tools_py.code_checker_tach
```

(These are added alongside the existing `code_checker_pytest`, `code_checker_pylint`, `code_checker_mypy`, `code_checker_ruff`, `code_checker_bandit` entries.)

## HOW

- Pure config change — no Python code modified.
- The `mcp_coder_utils_isolation` contract is untouched.
- Both modules added in the same commit per the issue's explicit requirement to fix the vulture gap together with adding tach.

## ALGORITHM

N/A — config edit.

## DATA

N/A — config edit.

## Tests

No unit tests. Verification is via `mcp__tools-py__run_lint_imports_check`:
- Layers contract: `Kept` ✓
- Forbidden external imports: `Kept` ✓
- mcp_coder_utils_isolation: `Kept` ✓

## Acceptance

- `run_lint_imports_check` — all three contracts pass.
- `run_pylint_check`, `run_pytest_check` (fast unit run), `run_mypy_check` — clean.
- One commit: `.importlinter` only.
