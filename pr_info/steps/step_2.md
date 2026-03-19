# Step 2: Simplify server.py run_pytest_check + defensive error handling + test updates

> **Context**: Read `pr_info/steps/summary.md` for the full issue overview. This step depends on Step 1 (`SanitizedArgs`, `sanitize_extra_args`).

## This step includes test_server_params.py updates to keep the test suite green.

---

## Part A: Simplify run_pytest_check signature

### WHERE
- **Modify**: `src/mcp_tools_py/server.py`

### WHAT — Remove parameters
Remove `verbosity` and `show_details` from the `run_pytest_check` function signature:

**Before:**
```python
def run_pytest_check(
    markers: Optional[List[str]] = None,
    verbosity: int = 2,
    extra_args: Optional[List[str]] = None,
    env_vars: Optional[Dict[str, str]] = None,
    show_details: bool = False,
) -> str:
```

**After:**
```python
def run_pytest_check(
    markers: Optional[List[str]] = None,
    extra_args: Optional[List[str]] = None,
    env_vars: Optional[Dict[str, str]] = None,
) -> str:
```

Update the docstring to remove `verbosity` and `show_details` descriptions. Mention that `-v`/`-vv`/`-vvv` can be passed via `extra_args` to control verbosity.

---

## Part B: Add new import

### WHERE
- **Modify**: `src/mcp_tools_py/server.py` (top imports section)

### WHAT
Add import of `sanitize_extra_args`:

```python
from mcp_tools_py.code_checker_pytest.utils import sanitize_extra_args
```

Note: `server.py` already imports from `mcp_tools_py.code_checker_pytest.reporting` and `mcp_tools_py.code_checker_pytest.runners`. Importing from `utils` is allowed by `tach.toml` (server depends on `code_checker_pytest`).

---

## Part C: Integrate sanitize_extra_args + always show details

### WHERE
- **Modify**: `src/mcp_tools_py/server.py`, inside `run_pytest_check` function body

### ALGORITHM (pseudocode for new function body)
```
1. Check tool availability (existing)
2. Call sanitize_extra_args(extra_args, markers) -> sanitized
3. Build final_extra_args = sanitized.cleaned_args + ["-s"]  (always add -s)
4. Call check_code_with_pytest(..., verbosity=sanitized.verbosity, extra_args=final_extra_args)
5. Call _format_pytest_result_with_details(test_results, show_details=True)  (always True)
6. If sanitized.notes: prepend notes to result, log them
7. Return result
```

### WHAT — Detailed changes inside the function body

**Replace** the current block:
```python
# Automatically add -s flag when show_details=True
final_extra_args = list(extra_args) if extra_args else []
if show_details and "-s" not in final_extra_args:
    final_extra_args.append("-s")

# Run pytest
test_results = check_code_with_pytest(
    ...
    verbosity=verbosity,
    extra_args=final_extra_args,
    ...
)

result = self._format_pytest_result_with_details(
    test_results, show_details
)
```

**With:**
```python
# Sanitize extra_args: deduplicate flags, extract verbosity
sanitized = sanitize_extra_args(extra_args, markers)

# Always add -s for print statement capture
final_extra_args = sanitized.cleaned_args + ["-s"]

# Log any deduplication notes
for note in sanitized.notes:
    structured_logger.info("extra_args sanitized", note=note)

# Run pytest
test_results = check_code_with_pytest(
    ...
    verbosity=sanitized.verbosity,
    extra_args=final_extra_args,
    ...
)

# Always show detailed failure output
result = self._format_pytest_result_with_details(
    test_results, show_details=True
)

# Prepend deduplication notes so LLM can self-correct
if sanitized.notes:
    notes_text = "\n".join(sanitized.notes)
    result = f"{notes_text}\n\n{result}"
```

---

## Part D: Wrap entire function body in defensive try/except

### WHERE
- **Modify**: `src/mcp_tools_py/server.py`, `run_pytest_check` function

### WHAT
The existing try/except **raises** on error. Change it to **return a string** instead:

**Before** (current except block):
```python
except Exception as e:
    logger.error(f"Error running pytest check: {str(e)}")
    structured_logger.error(...)
    raise
```

**After:**
```python
except Exception as e:
    error_msg = f"Unexpected error running pytest: {type(e).__name__}: {e}"
    logger.error(error_msg)
    structured_logger.error(
        "Pytest check failed",
        error=str(e),
        error_type=type(e).__name__,
        project_dir=str(self.project_dir),
    )
    return error_msg
```

### DATA
- **Return type**: Always `str`, never raises
- **Fallback format**: `"Unexpected error running pytest: {type}: {message}"`

---

## Part E: Update test_server_params.py

### WHERE
- **Modify**: `tests/test_server_params.py`

### WHAT — Remove tests that assert removed parameters

**Remove these tests** (they assert `verbosity`/`show_details` in the signature):
- `test_run_pytest_check_show_details_default_value` — asserts `show_details` in signature
- `test_server_method_signature_includes_show_details` — asserts `show_details` in signature
- `test_parameter_type_validation` — asserts `verbosity` annotation and default

**Remove `show_details`/`verbosity` assertions from these tests** (keep the tests, update assertions):
- `test_run_pytest_check_with_show_details_true` — remove `show_details=True` from call, keep rest of test logic
- `test_run_pytest_check_with_show_details_false` — remove `verbosity=1` from call, keep rest
- `test_show_details_with_focused_test_run` — simplify: both calls should now show detailed output (no more False->True toggle)
- `test_show_details_with_many_failures` — simplify similarly
- `test_show_details_output_length_limits` — remove `show_details=True` from call (always True now)
- `test_run_pytest_check_parameters` — remove `verbosity=3` from call, update mock assertion (no `verbosity` in call args)
- `test_run_pytest_check_backward_compatibility` — keep as-is (tests calling without optional params)
- `test_mcp_tool_decorator_compatibility` — keep as-is
- `test_enhanced_reporting_integration_preparation` — remove `show_details=True` from call

### WHAT — Update mock assertions for check_code_with_pytest calls

When tests mock `check_code_with_pytest` and assert call args, the `verbosity` value now comes from `sanitize_extra_args` (default 2), not from the function parameter:

```python
# Before:
mock_check.assert_called_once_with(
    ...
    verbosity=3,       # was passed as parameter
    extra_args=["--no-header"],
    ...
)

# After:
mock_check.assert_called_once_with(
    ...
    verbosity=2,       # default from sanitize_extra_args
    extra_args=["--no-header", "-s"],  # -s always appended
    ...
)
```

### WHAT — Add new tests

**Add test for simplified signature:**
```python
def test_run_pytest_check_simplified_signature():
    # Assert signature has: markers, extra_args, env_vars
    # Assert signature does NOT have: verbosity, show_details
```

**Add test for defensive error handling:**
```python
def test_run_pytest_check_never_raises():
    # Mock check_code_with_pytest to raise RuntimeError
    # Assert run_pytest_check returns a string (not raises)
    # Assert string contains "Unexpected error"
```

**Add test for deduplication notes in output:**
```python
def test_run_pytest_check_prepends_dedup_notes():
    # Call with extra_args=["-m", "slow"] AND markers=["unit"]
    # Assert result starts with "Note: -m flag in extra_args was ignored..."
```

### HOW
The existing test infrastructure (mock_server fixture, _get_tool helper) remains unchanged.
Tests that call `run_pytest_check` need to also mock or patch `sanitize_extra_args` where appropriate, or let it run naturally since it's a pure function.

---

## Verification
After this step:
- `pytest tests/test_code_checker_pytest/test_extra_args.py` still passes (Step 1 unaffected)
- `pytest tests/test_server_params.py` passes (test fixes included in this step)
- The server can be instantiated and `run_pytest_check` called with the new simplified signature
