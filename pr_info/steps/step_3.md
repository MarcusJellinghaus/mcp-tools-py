# Step 3: Improve error propagation in runners.py

> **Context**: Read `pr_info/steps/summary.md` for the full issue overview. This step is independent of Steps 1-2 and can be implemented in parallel.

---

## Part A: Include raw stderr/stdout in error messages

### WHERE
- **Modify**: `src/mcp_code_checker/code_checker_pytest/runners.py`

### WHAT
In `check_code_with_pytest()`, the except block currently returns only `str(e)`. Enhance it to include raw subprocess output when available from the exception context.

**Current code (lines ~290-300):**
```python
except Exception as e:
    structured_logger.error(
        "Pytest code check failed",
        error=str(e),
        error_type=type(e).__name__,
        project_dir=project_dir,
        test_folder=test_folder,
    )
    return {"success": False, "error": str(e)}
```

**Modified code:**
```python
except Exception as e:
    structured_logger.error(
        "Pytest code check failed",
        error=str(e),
        error_type=type(e).__name__,
        project_dir=project_dir,
        test_folder=test_folder,
    )
    error_message = str(e)
    return {"success": False, "error": error_message}
```

This is already mostly fine — the exceptions raised by `run_tests()` already include `combined_output` in their messages for exit codes 3, 4, >5. The main gap is exit codes 2 and 5.

### WHERE (in run_tests)
In `run_tests()`, the error messages for exit codes 2, 4, 5 should include the raw output:

**Improve the ValueError for exit code 5 / "no tests found":**

Current:
```python
raise ValueError(
    "No Tests Found: Pytest did not find any tests to run."
)
```

Enhanced:
```python
stderr_snippet = truncate_stderr(error_output.strip()) if error_output and error_output.strip() else ""
stdout_snippet = truncate_stderr(output.strip()) if output and output.strip() else ""
detail = ""
if stderr_snippet:
    detail += f" stderr: {stderr_snippet}"
if stdout_snippet:
    detail += f" stdout: {stdout_snippet}"
raise ValueError(
    f"No Tests Found: Pytest did not find any tests to run.{detail}"
)
```

Apply the same pattern to **both** "no tests found" raise sites (there are two in `run_tests()`).

### ALGORITHM (pseudocode)
```
1. Find all raise ValueError/RuntimeError sites in run_tests()
2. For each that doesn't already include combined_output/stderr:
   a. Append truncated stderr/stdout to the error message
   b. Use existing truncate_stderr() helper for safe length limiting
3. Keep existing error messages as the primary text, raw output as suffix
```

### HOW
- `truncate_stderr` is already imported from `mcp_code_checker.utils.subprocess_runner`
- No new imports needed
- No signature changes to `run_tests()` or `check_code_with_pytest()`

### DATA
- Error dict remains `{"success": False, "error": str}` — no structural change
- Error strings become more informative with appended stderr/stdout snippets

---

## Verification
After this step:
- `pytest tests/test_code_checker/test_runners.py` passes
- Error messages for "no tests found" now include raw output
- No changes to function signatures or return types
