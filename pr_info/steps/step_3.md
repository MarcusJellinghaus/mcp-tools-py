# Step 3: Redirect all direct `subprocess_runner` imports through the shim

**Summary:** [summary.md](./summary.md)

## Goal

Every `from mcp_coder_utils.subprocess_runner import ...` in production and test code becomes `from mcp_tools_py.utils.subprocess_runner import ...`. The shim (`src/mcp_tools_py/utils/subprocess_runner.py`) already re-exports everything needed.

## Test first

### WHERE
`tests/test_shim_reexports.py` (append to file created in step 1)

### WHAT
Verify key subprocess_runner symbols are the same objects as upstream:

```python
def test_subprocess_runner_reexports():
    from mcp_tools_py.utils.subprocess_runner import execute_command, CommandResult
    from mcp_coder_utils.subprocess_runner import (
        execute_command as u_ec,
        CommandResult as u_cr,
    )
    assert execute_command is u_ec
    assert CommandResult is u_cr
```

## Implementation

### WHAT
Mechanical prefix swap in ~15 files (11 src + 4 test). No logic changes, no signature changes.

### Pattern
```
BEFORE: from mcp_coder_utils.subprocess_runner import <symbols>
AFTER:  from mcp_tools_py.utils.subprocess_runner import <symbols>
```

### WHERE (all files requiring this change)

1. `src/mcp_tools_py/server.py`
2. `src/mcp_tools_py/checker_tools.py`
3. `src/mcp_tools_py/formatter/black_runner.py`
4. `src/mcp_tools_py/formatter/isort_runner.py`
5. `src/mcp_tools_py/refactoring/rope_tools.py`
6. `src/mcp_tools_py/code_checker_pylint/runners.py`
7. `src/mcp_tools_py/code_checker_pytest/runners.py`
8. `src/mcp_tools_py/code_checker_mypy/runners.py`
9. `src/mcp_tools_py/code_checker_ruff/runners.py`
10. `src/mcp_tools_py/code_checker_bandit/runners.py`
11. `src/mcp_tools_py/code_checker_vulture/runners.py`
12. `tests/conftest.py`
13. `tests/test_black_runner.py`
14. `tests/test_isort_runner.py`
15. `tests/test_error_transparency.py`

### ALGORITHM
```
1. For each file in the list above
2.   Find line: from mcp_coder_utils.subprocess_runner import ...
3.   Replace with: from mcp_tools_py.utils.subprocess_runner import ...
4.   (imported symbols stay exactly the same)
5. Run checks to confirm no breakage
```

## Verify

Run pylint, pytest, mypy — all must pass.

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_3.md.
Implement step 3: redirect all direct mcp_coder_utils.subprocess_runner imports
to go through the mcp_tools_py.utils.subprocess_runner shim, including 4 test files.
Add the shim identity test. This is a mechanical prefix swap — no logic changes.
Run all code quality checks after.
```
