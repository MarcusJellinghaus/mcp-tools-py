# Step 2: Simplify server.py run_pytest_check + defensive error handling

> **Context**: Read `pr_info/steps/summary.md` for the full issue overview. This step depends on Step 1 (`SanitizedArgs`, `sanitize_extra_args`).

## TDD: The existing tests in `test_server_params.py` will break after this change. Step 4 fixes them. Run `test_extra_args.py` from Step 1 to verify sanitization still works.

---

## Part A: Simplify run_pytest_check signature

### WHERE
- **Modify**: `src/mcp_code_checker/server.py`

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
- **Modify**: `src/mcp_code_checker/server.py` (top imports section)

### WHAT
Add import of `sanitize_extra_args`:

```python
from mcp_code_checker.code_checker_pytest.utils import sanitize_extra_args
```

Note: `server.py` already imports from `mcp_code_checker.code_checker_pytest.reporting` and `mcp_code_checker.code_checker_pytest.runners`. Importing from `utils` is allowed by `tach.toml` (server depends on `code_checker_pytest`).

---

## Part C: Integrate sanitize_extra_args + always show details

### WHERE
- **Modify**: `src/mcp_code_checker/server.py`, inside `run_pytest_check` function body

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
- **Modify**: `src/mcp_code_checker/server.py`, `run_pytest_check` function

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

## Verification
After this step:
- `pytest tests/test_code_checker_pytest/test_extra_args.py` still passes (Step 1 unaffected)
- Some tests in `test_server_params.py` will fail (they assert `verbosity`/`show_details` in signature) — fixed in Step 4
- The server can be instantiated and `run_pytest_check` called with the new simplified signature
