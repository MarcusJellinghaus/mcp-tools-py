# Step 1 — Surface pytest stdout/stderr on exit codes 3/4/>5

> **Reference**: see `pr_info/steps/summary.md` for problem statement, design notes, and rationale.

## Goal

Make `run_tests` include the actual pytest stdout/stderr in raised exceptions for exit codes **3** (internal error), **4** (usage error), and **>5** (plugin error), so LLM clients can diagnose the failure. Replace the prior `print()` calls with `logger.warning(...)` to retain server-side visibility.

## TDD order

1. **Write the failing test** in `tests/test_code_checker/test_runners.py` — parametrized over (returncode, label, exception_cls). Run it; expect failure (current code raises with no stderr/stdout snippet).
2. **Update the three error branches** in `src/mcp_tools_py/code_checker_pytest/runners.py`. Run the test; expect pass.
3. **Run quality gates** (pylint, pytest with `-n auto -m "not <integrations>"`, mypy). Fix anything that surfaces.
4. **Format** with `./tools/format_all.sh`, then stage + commit.

---

## WHERE

### File modified — runners.py
- **Path**: `src/mcp_tools_py/code_checker_pytest/runners.py`
- **Lines**: ~336–359 (three `elif` branches under the `if returncode != 0` block)

### File modified — test_runners.py
- **Path**: `tests/test_code_checker/test_runners.py`
- **Where**: New top-level test function. Place near the existing `test_run_tests_skip_default_test_folder` (line 317) — it follows the same `@patch("…runners.execute_command")` mock pattern.

---

## WHAT

### Implementation — `src/mcp_tools_py/code_checker_pytest/runners.py`

**Before** (lines 336–359, the three branches to change):

```python
elif process.returncode == 3:
    print(combined_output)
    raise RuntimeError(
        f"Internal Error: {error_context.exit_code_meaning if error_context else 'Pytest encountered an internal error'}. "
        f"Suggestion: {error_context.suggestion if error_context else 'Check pytest version compatibility'}"
    )
elif process.returncode == 4:
    print(combined_output)
    raise ValueError(
        f"Usage Error: {error_context.exit_code_meaning if error_context else 'Pytest was used incorrectly'}. "
        f"Suggestion: {error_context.suggestion if error_context else 'Verify command-line arguments'}"
    )
elif process.returncode == 5 and report_exists:
    # unchanged — keep as-is
    ...
elif process.returncode > 5:
    print(combined_output)
    raise RuntimeError(
        f"Plugin Error: {error_context.exit_code_meaning if error_context else f'Pytest plugin returned exit code {process.returncode}'}. "
        f"Suggestion: {error_context.suggestion if error_context else 'Check plugin documentation'}"
    )
```

**After**:

```python
elif process.returncode == 3:
    logger.warning("Pytest internal error (exit 3): %s", combined_output)
    raise RuntimeError(
        f"Internal Error: {error_context.exit_code_meaning}."
        f"{_build_error_detail(output, error_output)}"
    )
elif process.returncode == 4:
    logger.warning("Pytest usage error (exit 4): %s", combined_output)
    raise ValueError(
        f"Usage Error: {error_context.exit_code_meaning}."
        f"{_build_error_detail(output, error_output)}"
    )
elif process.returncode == 5 and report_exists:
    # unchanged
    ...
elif process.returncode > 5:
    logger.warning(
        "Pytest plugin error (exit %s): %s", process.returncode, combined_output
    )
    raise RuntimeError(
        f"Plugin Error: {error_context.exit_code_meaning}."
        f"{_build_error_detail(output, error_output)}"
    )
```

**Why `error_context.exit_code_meaning` is safe without a guard**: line 317–320 sets `error_context = create_error_context(...)` whenever `returncode != 0`, so all three branches are guaranteed to have a non-None `error_context`. The previous `if error_context else <fallback>` ternaries were dead code.

### Test — `tests/test_code_checker/test_runners.py`

```python
@pytest.mark.parametrize(
    "returncode, label, exc_cls",
    [
        (3, "Internal Error", RuntimeError),
        (4, "Usage Error", ValueError),
        (6, "Plugin Error", RuntimeError),
    ],
)
@patch("mcp_tools_py.code_checker_pytest.runners.execute_command")
def test_run_tests_surfaces_pytest_output_on_error_exit_codes(
    mock_execute: MagicMock,
    returncode: int,
    label: str,
    exc_cls: type[Exception],
) -> None:
    """Exit codes 3, 4, >5 must include pytest stdout/stderr in the raised exception."""
    mock_result = MagicMock()
    mock_result.return_code = returncode
    mock_result.stdout = "STDOUT_MARKER_xyz"
    mock_result.stderr = "STDERR_MARKER_abc"
    mock_result.execution_error = None
    mock_result.timed_out = False
    mock_execute.return_value = mock_result

    with pytest.raises(exc_cls) as excinfo:
        run_tests("/test/project", "tests", python_executable=sys.executable)

    msg = str(excinfo.value)
    assert label in msg
    assert "STDERR_MARKER_abc" in msg
    assert "STDOUT_MARKER_xyz" in msg
```

Imports already present at top of file (`pytest`, `MagicMock`, `patch`, `sys`, `run_tests`).

---

## HOW (integration points)

- **No new imports** in `runners.py`. `logger` (line 44) and `_build_error_detail` (line 26) are already in scope.
- **No new imports** in `test_runners.py`. Uses existing `pytest`, `MagicMock`, `patch`, `sys`, `run_tests`.
- **No public API change**: exception types (`RuntimeError` / `ValueError`) and labels (`"Internal Error"` / `"Usage Error"` / `"Plugin Error"`) are preserved. Only the trailing `"Suggestion: …"` text is replaced with the `stderr:`/`stdout:` snippet.
- **No config / decorator / dependency changes.**

---

## ALGORITHM (per branch)

```
on returncode in {3, 4, >5}:
    log combined stdout+stderr at WARNING level (server-side visibility)
    detail = _build_error_detail(stdout, stderr)   # truncated, prefixed " stderr: …  stdout: …"
    raise <Exc>(f"<Label>: {error_context.exit_code_meaning}.{detail}")
```

`_build_error_detail` (already in the file, lines 26–41) handles empty output, applies `truncate_stderr()` defaults, and produces the exact format expected.

---

## DATA

### Return values
- **Unchanged.** All three branches still raise; no successful return path is touched.

### Exception message structure
```
"<Label>: <exit_code_meaning>. stderr: <truncated stderr> stdout: <truncated stdout>"
```
- `<Label>` ∈ {`Internal Error`, `Usage Error`, `Plugin Error`}.
- `<exit_code_meaning>` from `error_context.exit_code_meaning` (set by `create_error_context` in `utils.py`).
- `stderr` / `stdout` segments produced by `_build_error_detail` (each prefixed with leading space; either may be empty).

### Log records
- Logger: `mcp_tools_py.code_checker_pytest.runners` (already-bound `logger`).
- Level: `WARNING`.
- Format: `"Pytest <kind> error (exit <N>): <combined stdout+stderr>"`.

---

## Quality gates (must all pass before commit)

```python
mcp__tools-py__run_pylint_check()
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto", "-m",
    "not git_integration and not claude_cli_integration and not claude_api_integration "
    "and not formatter_integration and not github_integration and not langchain_integration"])
mcp__tools-py__run_mypy_check()
```

Then `./tools/format_all.sh` → `git add` → `git commit`.

---

## LLM prompt for this step

> Implement Step 1 from `pr_info/steps/step_1.md` (refer to `pr_info/steps/summary.md` for context).
>
> Follow TDD: first add the parametrized test `test_run_tests_surfaces_pytest_output_on_error_exit_codes` to `tests/test_code_checker/test_runners.py` and confirm it fails against the current code. Then update the three error branches (`returncode == 3`, `== 4`, `> 5`) in `src/mcp_tools_py/code_checker_pytest/runners.py` per the WHAT section: replace `print(combined_output)` with `logger.warning(...)`, replace the canned `Suggestion: …` text with `_build_error_detail(output, error_output)`, and drop the `if error_context else <fallback>` ternaries (`error_context` is guaranteed non-None at these branches per lines 317–320). Reuse existing helpers — do not reimplement.
>
> Run all three quality gates (pylint, pytest with the standard `-n auto` + integration-marker exclusions, mypy) and confirm green. Run `./tools/format_all.sh`, stage the two modified files, and produce one commit with a message describing the bug fix and referencing issue #187.
>
> Do not modify any other checker runners (pylint, mypy, ruff, etc.) — that audit is out of scope per the issue.
