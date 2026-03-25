# Step 5: Robustness improvements — error handling in rope_cli.py

**Summary**: See `pr_info/steps/summary.md` for full context (Issue #112).

Harden `rope_cli.py` so that unhandled exceptions produce structured JSON errors
instead of raw tracebacks, and surface rope's stderr warnings alongside
successful results.

## WHERE: Files to modify

| File | Action |
|------|--------|
| `src/mcp_tools_py/refactoring/rope_cli.py` | Add error handling |
| `src/mcp_tools_py/refactoring/rope_tools.py` | Forward stderr on success |
| `tests/test_refactoring/test_rope_tools.py` | Add tests for error cases |

## WHAT: Specific changes

### 1. Catch unhandled exceptions in `rope_cli.py::main()`

**Current behavior**: If `_rename_symbol_impl` (or any `_*_impl`) raises an
exception that isn't caught by its own `try/except`, the subprocess crashes
with a Python traceback on stderr and exit code 1. `_run_rope_subprocess()`
reports this as `Error running rename_symbol (exit 1): <raw traceback>` —
which is hard to read.

**Change**: Wrap the dispatch logic in a `try/except`:

```python
def main() -> None:
    # ... parse args, dispatch ...
    try:
        if operation == "rename_symbol":
            result = _rename_symbol_impl(...)
        elif ...
    except Exception as exc:
        print(json.dumps({"error": f"{type(exc).__name__}: {exc}"}))
        sys.exit(1)

    print(json.dumps({"result": result}))
```

Then in `_run_rope_subprocess()`, check for the `"error"` key:

```python
try:
    output = json.loads(result.stdout)
    if "error" in output:
        return f"Error in {operation}: {output['error']}"
    return str(output["result"])
except (json.JSONDecodeError, KeyError):
    ...
```

### 2. Safety net around `json.dumps()` in `rope_cli.py`

**Current behavior**: If the rope result contains characters that somehow
break JSON serialization (extremely unlikely but possible with binary content
in error messages), `json.dumps()` would raise and the subprocess would crash
without structured output.

**Change**: Wrap the final `print(json.dumps(...))` in a `try/except`:

```python
try:
    print(json.dumps({"result": result}))
except (TypeError, ValueError):
    # Fallback: output raw result with a marker
    print(result)
    sys.exit(0)
```

### 3. Include truncated stderr on success in `_run_rope_subprocess()`

**Current behavior**: On success (exit code 0), stderr is ignored. But rope
and Python may emit warnings to stderr (deprecation warnings, rope logging)
that are useful for debugging.

**Change**: In `_run_rope_subprocess()`, after successfully parsing the JSON
result, append truncated stderr if non-empty:

```python
result_str = str(output["result"])
if result.stderr.strip():
    # Include warnings/logs for debugging (truncated)
    stderr_preview = result.stderr.strip()[:200]
    logger.debug("rope subprocess stderr: %s", stderr_preview)
return result_str
```

Use `logger.debug()` rather than appending to the user-visible result — keep
the tool output clean but make warnings available in logs.

### 4. Tests

Add to `tests/test_refactoring/test_rope_tools.py`:

**Test: rope_cli structured error on exception**
```python
def test_rope_cli_returns_json_error_on_exception(tmp_path):
    """rope_cli should return JSON error, not raw traceback."""
    # Call rename_symbol on a file with syntax errors
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def (broken syntax")
    result = rename_symbol(tmp_path, "bad.py", "whatever", "new_name")
    assert "Error" in result  # Should be a clean error, not a traceback
```

**Test: rope_cli handles unknown operation**
```python
def test_rope_cli_unknown_operation():
    """rope_cli should exit 1 on unknown operation."""
    import subprocess
    proc = subprocess.run(
        [sys.executable, "-m", "mcp_tools_py.refactoring.rope_cli",
         "unknown_op", '{}'],
        capture_output=True, text=True
    )
    assert proc.returncode == 1
    assert "Unknown operation" in proc.stderr
```

## VERIFY

After all changes:

1. Run quality checks: pylint, pytest (`-n auto -m "not integration"`), mypy
2. Run integration tests: `pytest tests/test_refactoring/ -v`
3. Manual smoke test via MCP: call `rename_symbol` with a nonexistent symbol
   and verify clean error output

## Commit message
```
fix(refactoring): add structured error handling to rope subprocess CLI
```
