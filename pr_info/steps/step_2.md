# Step 2: Integrate helper into `run_lint_imports_check` and update integration test

> **Context:** See `pr_info/steps/summary.md` for full issue context (Issue #139).

## LLM Prompt

Wire `_strip_lint_imports_header()` (added in Step 1) into the `run_lint_imports_check` tool so its output is stripped before returning. Update the existing integration test to verify the banner is removed end-to-end. Run all code quality checks (pylint, pytest, mypy) and fix any issues before committing.

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/checker_tools.py` | Call `_strip_lint_imports_header()` in `run_lint_imports_check` |
| `tests/test_checker_tools.py` | Update `test_lint_imports_success_returns_raw_output` to use banner-containing input |

## WHAT

One-line change in `run_lint_imports_check` inner function inside `_register_lint_imports`.

## HOW

In `checker_tools.py`, in `_register_lint_imports` → `run_lint_imports_check`, change the return line from:

```python
return output.strip() or "lint-imports produced no output."
```

to:

```python
output = _strip_lint_imports_header(output)
return output or "lint-imports produced no output."
```

Note: `_strip_lint_imports_header` already calls `.strip()` internally, so the explicit `.strip()` is no longer needed.

## DATA

- No new data structures. The return type remains `str`.

## Integration test update in `tests/test_checker_tools.py`

Update `test_lint_imports_success_returns_raw_output`:
- Change the mocked `stdout` to include the ASCII banner + dashed separators + `Contracts: 2 kept, 0 broken`
- Assert the result does **not** contain box-drawing characters
- Assert the result **does** contain `Contracts: 2 kept, 0 broken`

## Commit

```
feat: strip lint-imports ASCII banner from tool output (#139)
```
