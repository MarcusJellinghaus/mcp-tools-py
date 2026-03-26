# Step 5: Manual test plan update

> **Context**: See [summary.md](summary.md) for full issue overview.

## Goal

Update the manual test plan to reflect the new `symbol_names` signature and add
batch move test cases.

## WHERE

| File | Section |
|------|---------|
| `tests/mcp_tools_py_manual/TEST_PLAN.md` | Test 7 (move_symbol) |

## WHAT

### Update Test 7a–7c — use `symbol_names` parameter

Change all `move_symbol` calls from `symbol_name="X"` to `symbol_names=["X"]`.

**Test 7a (single symbol dry run):**
```
move_symbol(source_file="...", symbol_names=["format_user"], dest_file="...", dry_run=True)
```

**Test 7b (single symbol apply):**
```
move_symbol(source_file="...", symbol_names=["format_user"], dest_file="...", dry_run=False)
```

**Test 7c (single symbol teardown):** unchanged.

### Add Tests 7d–7f — Batch move (new)

**Target**: Move `create_user` and `is_active` from `utils.py` → new `user_ops.py`.

**7d — Batch dry run:**
```
move_symbol(
    source_file="tests/mcp_tools_py_manual/sample_project/utils.py",
    symbol_names=["create_user", "is_active"],
    dest_file="tests/mcp_tools_py_manual/sample_project/user_ops.py",
    dry_run=True
)
```
Expected: Preview shows both symbols, no files modified.

**7e — Batch apply:**
```
move_symbol(
    source_file="tests/mcp_tools_py_manual/sample_project/utils.py",
    symbol_names=["create_user", "is_active"],
    dest_file="tests/mcp_tools_py_manual/sample_project/user_ops.py",
    dry_run=False
)
```
Expected:
- Both symbols moved to `user_ops.py`
- Order in destination: `create_user` appears before `is_active`
- Imports updated in `services.py` and test files
- Result includes review reminder notes
- All tests pass after move

**Verify:**
1. `list_symbols(file="...user_ops.py")` — shows `create_user`, `is_active`
2. `list_symbols(file="...utils.py")` — shows only `format_user`
3. `run_pytest_check(extra_args=["tests/mcp_tools_py_manual/", "-v"])` — all 11 tests pass

**7f — Batch teardown:** Delete `sample_project/` and recreate.

### Update PROGRESS_TRACKER.md

Add rows for Tests 7d, 7e, 7f (dry, apply, verify, teardown).

## LLM PROMPT

```
Implement Step 5 from pr_info/steps/step_5.md (see pr_info/steps/summary.md for context).

Update tests/mcp_tools_py_manual/TEST_PLAN.md:
1. Change all move_symbol calls in Test 7a/7b from symbol_name="X" to symbol_names=["X"]
2. Add Tests 7d (batch dry run), 7e (batch apply), 7f (batch teardown)
3. Update PROGRESS_TRACKER.md template with rows for Tests 7d–7f

After making changes, run all three code quality checks (pylint, pytest unit tests, mypy).
Fix any issues before committing. Commit message: "docs(test-plan): update move_symbol tests for batch signature"
```
