# Step 2: Redirect all direct `log_utils` imports through the shim

**Summary:** [summary.md](./summary.md)

## Goal

Every `from mcp_coder_utils.log_utils import ...` in production code becomes `from mcp_tools_py.log_utils import ...`. The shim (`src/mcp_tools_py/log_utils.py`) already re-exports everything needed.

## Test first

### WHERE
`tests/test_shim_reexports.py` (append to file created in step 1)

### WHAT
Verify all three log_utils symbols are the same objects as upstream:

```python
def test_log_utils_reexports():
    from mcp_tools_py.log_utils import OUTPUT, log_function_call, setup_logging
    from mcp_coder_utils.log_utils import (
        OUTPUT as u_OUTPUT,
        log_function_call as u_lfc,
        setup_logging as u_sl,
    )
    assert OUTPUT is u_OUTPUT
    assert log_function_call is u_lfc
    assert setup_logging is u_sl
```

## Implementation

### WHAT
Mechanical prefix swap in ~12 files. No logic changes, no signature changes.

### Pattern
```
BEFORE: from mcp_coder_utils.log_utils import <symbols>
AFTER:  from mcp_tools_py.log_utils import <symbols>
```

### WHERE (all files requiring this change)

1. `src/mcp_tools_py/main.py`
2. `src/mcp_tools_py/server.py`
3. `src/mcp_tools_py/checker_tools.py`
4. `src/mcp_tools_py/utility_tools.py`
5. `src/mcp_tools_py/inspect_library.py`
6. `src/mcp_tools_py/formatter/formatter_tools.py`
7. `src/mcp_tools_py/refactoring/__init__.py`
8. `src/mcp_tools_py/code_checker_pylint/runners.py`
9. `src/mcp_tools_py/code_checker_pylint/reporting.py`
10. `src/mcp_tools_py/code_checker_pytest/runners.py`
11. `src/mcp_tools_py/code_checker_pytest/reporting.py`
12. `src/mcp_tools_py/code_checker_mypy/runners.py`
13. `src/mcp_tools_py/code_checker_ruff/runners.py`
14. `src/mcp_tools_py/code_checker_bandit/runners.py`

### ALGORITHM
```
1. For each file in the list above
2.   Find line: from mcp_coder_utils.log_utils import ...
3.   Replace with: from mcp_tools_py.log_utils import ...
4.   (imported symbols stay exactly the same)
5. Run checks to confirm no breakage
```

## Verify

Run pylint, pytest, mypy — all must pass.

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_2.md.
Implement step 2: redirect all direct mcp_coder_utils.log_utils imports
to go through the mcp_tools_py.log_utils shim. Add the shim identity test.
This is a mechanical prefix swap — no logic changes. Run all code quality checks after.
```
