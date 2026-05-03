# Step 1 — Stop swallowing pytest output in `run_tests`

> **Reference**: see `pr_info/steps/summary.md` for problem statement, design notes, and rationale.

## Goal

Make `run_tests` (in `src/mcp_tools_py/code_checker_pytest/runners.py`) stop dumping pytest output to the MCP server's stdout via `print()`. **Every `print()` call site inside `run_tests` is replaced** — pytest-output / failure-diagnostic prints become `logger.warning(...)`, operational status chatter becomes `logger.debug(...)`, and the tautological line-309 print is **deleted entirely**. Additionally, **every error path that raises must surface the real pytest stdout/stderr to the LLM caller through the raised exception text** (the MCP path is `{"success": False, "error": str(e)}`, so only the exception message reaches the client). The pattern is `_build_error_detail(stdout, stderr)` appended inline to the exception message — already correct at line 311, and added here at:

- line 217 (`raise RuntimeError(subprocess_result.execution_error)`) — append `_build_error_detail(subprocess_result.stdout, subprocess_result.stderr)`. Verified against source: `execution_error` is a separate string field on `CommandResult` and does **not** include stdout/stderr, so they must be appended explicitly.
- line 223 (`raise TimeoutError(f"Subprocess timed out: ...")`) — append `_build_error_detail(subprocess_result.stdout, subprocess_result.stderr)`. The same `subprocess_result` object carries any partial stdout/stderr captured by `subprocess_runner` before the timeout fired.
- line 271 (`pytest-json-report` install failure → `RuntimeError`)
- line 289 (retry timed out → `TimeoutError`)
- lines 337 / 343 / 355 (exit codes 3 / 4 / >5)
- line 384 (no-report-file `RuntimeError`; currently includes stderr only — extend to also include stdout)

Final raising-path set: 217, 223, 271, 289, 337, 343, 355, 384. No new helper / abstraction — match the existing inline pattern at line 311.

## TDD order

1. **Write the failing test(s)** in `tests/test_code_checker/test_runners.py` — parametrized coverage over **all eight raising paths** (217 execution-error, 223 timeout, 271 install fail, 289 retry timeout, 337/343/355 exit codes 3/4/>5, 384 no-report) using pytest's `caplog` fixture. Each case asserts the raised exception text carries `STDERR_MARKER` and (where applicable) `STDOUT_MARKER`, plus a matching `WARNING`-level log record where one is emitted. Split into two parametrized families if mock setup diverges enough between the install/retry cases and the simple-returncode/early-raise cases that one parametrize gets ugly — engineer's call, prefer fewer tests. Suggested split: `test_run_tests_surfaces_pytest_output_on_error_exit_codes` for 217/223/337/343/355/384, `test_run_tests_surfaces_pytest_output_on_install_and_retry_failures` for 271/289. Run them; expect failure.
2. **Update `run_tests`** in `src/mcp_tools_py/code_checker_pytest/runners.py`:
   - replace every `print()` inside the function — pytest-output / diagnostic sites (~230 timeout-warning, 271 install-fail, 289 retry-timeout, 304 install/retry handler, ~363 no-report dump, 416–418 outer handler) become `logger.warning(...)`; operational sites (~210 command echo, ~221 return-code echo, ~247 plugin-not-found, ~278 installed-retrying) become `logger.debug(...)`; **delete the line-309 `print("No tests found, raising specific exception")`** — the next-line `raise ValueError(...)` (which already calls `_build_error_detail`) is self-explanatory;
   - at line 217 (execution-error raise), append `_build_error_detail(subprocess_result.stdout, subprocess_result.stderr)` to the `RuntimeError` message;
   - at line 223 (subprocess-timeout raise), append `_build_error_detail(subprocess_result.stdout, subprocess_result.stderr)` to the `TimeoutError` message;
   - at line 271 (install fail), append `_build_error_detail(install_result.stdout, install_result.stderr)` to the `RuntimeError` message;
   - at line 289 (retry timeout), append `_build_error_detail(retry_result.stdout, retry_result.stderr)` to the `TimeoutError` message;
   - at lines 337/343/355 (exit codes 3/4/>5), append `_build_error_detail(output, error_output)` to the exception message and drop canned `Suggestion: …` text + dead `error_context` ternaries;
   - at line 384 (no-report-file `RuntimeError`), extend `base_msg` to use `_build_error_detail(output, error_output)` so stdout is also included (currently only stderr is appended).

   Run the tests; expect pass.
3. **Run quality gates** (pylint, pytest with `-n auto -m "not integration"`, mypy). Fix anything that surfaces.
4. **Format with `mcp__mcp-tools-py__run_format_code`**, then `git add` the two modified files and `git commit`.

---

## WHERE

### File modified — runners.py
- **Path**: `src/mcp_tools_py/code_checker_pytest/runners.py`
- **`print()` call sites inside `run_tests` to convert or delete** (line numbers approximate):
  - ~210 — `print(f"Running command: ...")` (debug command echo) → `logger.debug(...)`
  - ~221 — `print(f"Command completed with return code: ...")` (debug echo) → `logger.debug(...)`
  - ~230 — `print(f"Command timed out after ...")` (real failure path; fired right before raising the line-223 `TimeoutError`) → `logger.warning(...)`
  - ~247 — `print("pytest-json-report plugin not found, attempting to install it...")` (operational status) → `logger.debug(...)`
  - ~271 — `pytest-json-report` install failure → `logger.warning(...)`; also gains `_build_error_detail(install_result.stdout, install_result.stderr)` in the `RuntimeError` message
  - ~278 — `print("Installed pytest-json-report, retrying...")` (operational status) → `logger.debug(...)`
  - ~289 — retry timed out → `logger.warning(...)`; also gains `_build_error_detail(retry_result.stdout, retry_result.stderr)` in the `TimeoutError` message
  - ~304 — install / retry error handler → `logger.warning(...)`
  - ~309 — `print("No tests found, raising specific exception")` → **deleted** (tautological with the next-line `raise ValueError(...)`, which already appends `_build_error_detail(...)`)
  - ~337 — `returncode == 3` (internal error) → `logger.warning(...)`; also gains `_build_error_detail` in the raised message
  - ~343 — `returncode == 4` (usage error) → `logger.warning(...)`; also gains `_build_error_detail` in the raised message
  - ~355 — `returncode > 5` (plugin error) → `logger.warning(...)`; also gains `_build_error_detail` in the raised message
  - ~363 — `print(combined_output)` in the no-report-file fallback (this print and the line-384 `raise RuntimeError(base_msg)` are the **same** branch — the print dumps swallowed pytest output right before the raise) → `logger.warning(...)`
  - ~416–418 — outer error handler (multi-line `print`) → `logger.warning(...)`
- **Non-`print` raise sites that also gain `_build_error_detail`**:
  - ~217 — `raise RuntimeError(subprocess_result.execution_error)`. Verified: `execution_error` is a separate string field on `CommandResult` and does not contain stdout/stderr — append `_build_error_detail(subprocess_result.stdout, subprocess_result.stderr)`.
  - ~223 — `raise TimeoutError(f"Subprocess timed out: ...")`. Append `_build_error_detail(subprocess_result.stdout, subprocess_result.stderr)`; partial output is on the same `subprocess_result`.
  - ~384 — final no-report-file `RuntimeError`. Currently `base_msg` only appends ` stderr: <truncated>`; extend to use `_build_error_detail(output, error_output)` so stdout is also surfaced.

### File modified — test_runners.py
- **Path**: `tests/test_code_checker/test_runners.py`
- **Where**: New top-level test function(s). Place them **after `test_run_tests_skip_default_test_folder` and its sibling `test_run_tests_default_test_folder_appended`** (currently around lines 317 and 344) to keep the parametrized-mock cluster together — same `@patch("…runners.execute_command")` pattern.
- **Scope**: parametrized coverage of **all eight error paths that raise** (217, 223, 271, 289, 337, 343, 355, 384). Suggested split into two parametrized tests when `execute_command` mock setup diverges enough between the install/retry path (needs `side_effect` returning two/three results) and the simple-returncode/early-raise branches — engineer's call, prefer fewer tests. The remaining `print`-only branches that don't raise (~210/~221/~247/~278 debug echoes, 304 install error handler, ~363 no-report dump, 416–418 outer error handler) are **not** separately covered — converting their `print` to logger calls is mechanical and low-risk, and remains within the existing test file's surrounding-path coverage. Keeps the test file tidy.

---

## WHAT

### Implementation — `src/mcp_tools_py/code_checker_pytest/runners.py`

**Mechanical `print` → logger replacements** (preserve existing message text; switch to `%s`-style format args where interpolation is involved). The level is per-site explicit:

```python
# ~210 — debug command echo
logger.debug("Running command: %s", " ".join(command))

# ~221 — debug return-code echo
logger.debug("Command completed with return code: %s", subprocess_result.return_code)

# ~230 — real failure (fired right before the line-223 TimeoutError raise)
logger.warning(
    "Command timed out after %s seconds: %s", timeout_seconds, " ".join(command)
)

# ~247 — operational status
logger.debug("pytest-json-report plugin not found, attempting to install it...")

# ~278 — operational status
logger.debug("Installed pytest-json-report, retrying...")

# ~304 — install / retry error handler
logger.warning("Error during installation or retry: %s", install_error)

# ~309 — DELETED ENTIRELY (tautological with the next-line raise)

# ~363 — swallowed pytest output dumped right before the line-384 raise
logger.warning("Pytest produced no report file: %s", combined_output)

# ~416–418  (was a 3-line f-string print)
logger.warning(
    "Error during pytest execution: folder=%s command=%s",
    project_dir,
    command_line,
)
```

**Early-raise paths (~217 and ~223)** — append `_build_error_detail(...)` so the LLM caller sees real stdout/stderr:

**Before**:

```python
# ~217
if subprocess_result.execution_error:
    raise RuntimeError(subprocess_result.execution_error)

# ~223
if subprocess_result.timed_out:
    print(f"Command timed out after {timeout_seconds} seconds: {' '.join(command)}")
    raise TimeoutError(f"Subprocess timed out: {' '.join(command)}")
```

**After**:

```python
# ~217 — execution_error is a separate string field on CommandResult; it does not contain
# stdout/stderr, so they must be appended explicitly.
if subprocess_result.execution_error:
    detail = _build_error_detail(
        subprocess_result.stdout, subprocess_result.stderr
    )
    raise RuntimeError(f"{subprocess_result.execution_error}{detail}")

# ~223 — partial stdout/stderr captured before timeout is on the same subprocess_result.
if subprocess_result.timed_out:
    logger.warning(
        "Command timed out after %s seconds: %s",
        timeout_seconds,
        " ".join(command),
    )
    detail = _build_error_detail(
        subprocess_result.stdout, subprocess_result.stderr
    )
    raise TimeoutError(
        f"Subprocess timed out: {' '.join(command)}.{detail}"
    )
```

**Install-failure branch (~271)** — convert `print` to `logger.warning` **and** include real install stderr/stdout in the raised exception:

**Before**:

```python
if (
    install_result.return_code != 0
    or install_result.execution_error
):
    print(
        f"Failed to install pytest-json-report: {install_result.stderr}"
    )
    raise RuntimeError(
        "Failed to install the required pytest-json-report plugin"
    )
```

**After**:

```python
if (
    install_result.return_code != 0
    or install_result.execution_error
):
    logger.warning(
        "Failed to install pytest-json-report: %s", install_result.stderr
    )
    detail = _build_error_detail(install_result.stdout, install_result.stderr)
    raise RuntimeError(
        f"Failed to install the required pytest-json-report plugin.{detail}"
    )
```

**Retry-timeout branch (~289)** — convert `print` to `logger.warning` **and** include retry stdout/stderr in the raised exception:

**Before**:

```python
if retry_result.timed_out:
    print("Retry timed out")
    raise TimeoutError(
        "Timed out while retrying the test after installing pytest-json-report"
    )
```

**After**:

```python
if retry_result.timed_out:
    logger.warning("Retry timed out")
    detail = _build_error_detail(retry_result.stdout, retry_result.stderr)
    raise TimeoutError(
        f"Timed out while retrying the test after installing pytest-json-report.{detail}"
    )
```

**Three exit-code branches** (lines ~336–359) — convert `print` to `logger.warning` **and** rewrite the exception message:

**Before**:

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

**No-report-file branch (~378–384)** — extend `base_msg` so stdout is also surfaced (currently only stderr is included):

**Before**:

```python
base_msg = (
    "Test execution completed but no report file was generated. "
    "Check for configuration errors in pytest.ini or pytest plugins."
)
if stderr.strip():
    base_msg += f" stderr: {truncate_stderr(stderr.strip())}"
raise RuntimeError(base_msg)
```

**After**:

```python
base_msg = (
    "Test execution completed but no report file was generated. "
    "Check for configuration errors in pytest.ini or pytest plugins."
)
base_msg += _build_error_detail(output, error_output)
raise RuntimeError(base_msg)
```

`_build_error_detail` already handles the empty-stderr / empty-stdout cases gracefully (returns "" or includes only the populated half), and applies the same `truncate_stderr` defaults — so the previous `if stderr.strip()` guard becomes redundant.

### Test — `tests/test_code_checker/test_runners.py`

**Test #1 — early-raise paths (217, 223), exit-code branches (3, 4, >5), and no-report-file (line 384)**. Most cases need only a single `execute_command` mock return because they branch on `process.returncode` / `report_exists` / fields on the first `subprocess_result`. The no-report-file row additionally needs `os.path.isfile` patched (verified against source line 323: `report_exists = os.path.isfile(temp_report_file)`) so the report-existence check returns `False`.

> Snippet below is **illustrative; rewrite at implementation time, do not copy-paste.**

```python
@pytest.mark.parametrize(
    "case_id, returncode, execution_error, timed_out, report_exists, label, exc_cls, log_substring",
    [
        # case_id, rc, exec_err, timed_out, report_exists, label, exc_cls, log_substring (or None if no warning expected)
        ("execution_error", 0, "subprocess crashed: signal 9", False, True, "subprocess crashed", RuntimeError, None),
        ("subprocess_timeout", 0, None, True, True, "Subprocess timed out", TimeoutError, "command timed out after"),
        ("internal_error_3", 3, None, False, True, "Internal Error", RuntimeError, "internal error (exit 3)"),
        ("usage_error_4",    4, None, False, True, "Usage Error",    ValueError,   "usage error (exit 4)"),
        ("plugin_error_6",   6, None, False, True, "Plugin Error",   RuntimeError, "plugin error (exit 6)"),
        # No-report-file: returncode that bypasses the earlier branches (e.g. 0) AND os.path.isfile patched to False.
        ("no_report_file",   0, None, False, False, "no report file was generated", RuntimeError, "produced no report file"),
    ],
)
@patch("mcp_tools_py.code_checker_pytest.runners.execute_command")
def test_run_tests_surfaces_pytest_output_on_error_exit_codes(
    mock_execute: MagicMock,
    caplog: pytest.LogCaptureFixture,
    case_id: str,
    returncode: int,
    execution_error: str | None,
    timed_out: bool,
    report_exists: bool,
    label: str,
    exc_cls: type[Exception],
    log_substring: str | None,
) -> None:
    """All early-raise / exit-code / no-report-file paths must include pytest
    stdout/stderr in the raised exception AND emit a matching WARNING log
    record where applicable (no print to stdout)."""
    mock_result = MagicMock(
        return_code=returncode,
        stdout="STDOUT_MARKER_xyz",
        stderr="STDERR_MARKER_abc",
        execution_error=execution_error,
        timed_out=timed_out,
    )
    mock_execute.return_value = mock_result

    with caplog.at_level(
        logging.WARNING, logger="mcp_tools_py.code_checker_pytest.runners"
    ), patch(
        "mcp_tools_py.code_checker_pytest.runners.os.path.isfile",
        return_value=report_exists,
    ):
        with pytest.raises(exc_cls) as excinfo:
            run_tests("/test/project", "tests", python_executable=sys.executable)

    # Exception carries the diagnostic snippet (the line-217 execution_error
    # case may not include STDOUT/STDERR if subprocess_runner did not capture
    # them — engineer should adjust assertion strictness per case).
    msg = str(excinfo.value)
    assert label in msg
    assert "STDERR_MARKER_abc" in msg
    assert "STDOUT_MARKER_xyz" in msg

    # And a WARNING was logged for branches that emit one (no print-to-stdout regression)
    if log_substring is not None:
        matching = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING
            and log_substring in r.getMessage().lower()
        ]
        assert matching, f"expected WARNING for case {case_id}"
```

**Test #2 — install-failure (line 271) and retry-timeout (line 289)**. These need `execute_command` to return multiple sequential results via `mock_execute.side_effect`. The first call is always the original pytest invocation that fails with the missing-plugin signature (triggers the install/retry block); subsequent calls then diverge per branch.

> Snippet below is **illustrative; rewrite at implementation time, do not copy-paste.**

```python
@pytest.mark.parametrize(
    "second_kind, exc_cls, msg_substring, log_substring",
    [
        (
            "install_fail",
            RuntimeError,
            "Failed to install the required pytest-json-report plugin",
            "failed to install pytest-json-report",
        ),
        (
            "retry_timeout",
            TimeoutError,
            "Timed out while retrying",
            "retry timed out",
        ),
    ],
)
@patch("mcp_tools_py.code_checker_pytest.runners.execute_command")
def test_run_tests_surfaces_pytest_output_on_install_and_retry_failures(
    mock_execute: MagicMock,
    caplog: pytest.LogCaptureFixture,
    second_kind: str,
    exc_cls: type[Exception],
    msg_substring: str,
    log_substring: str,
) -> None:
    """Install-failure (line 271) and retry-timeout (line 289) must include
    real stdout/stderr in the raised exception AND emit a WARNING."""
    # First call: pytest exits with the missing-plugin signature so the
    # install/retry block fires.
    first = MagicMock(
        return_code=4,
        stdout="",
        stderr="ModuleNotFoundError: pytest_jsonreport",
        execution_error=None,
        timed_out=False,
    )

    # Build the side_effect sequence per branch.
    if second_kind == "install_fail":
        # Second call is the failing `pip install`. Its stdout/stderr must
        # surface in the raised RuntimeError.
        install_fail = MagicMock(
            return_code=1,
            stdout="STDOUT_MARKER_xyz",
            stderr="STDERR_MARKER_abc",
            execution_error=None,
            timed_out=False,
        )
        mock_execute.side_effect = [first, install_fail]
    else:  # retry_timeout
        # Install succeeds, then the retry pytest call times out. The retry
        # result's stdout/stderr must surface in the raised TimeoutError.
        install_ok = MagicMock(
            return_code=0,
            stdout="",
            stderr="",
            execution_error=None,
            timed_out=False,
        )
        retry_timeout = MagicMock(
            return_code=None,
            stdout="STDOUT_MARKER_xyz",
            stderr="STDERR_MARKER_abc",
            execution_error=None,
            timed_out=True,
        )
        mock_execute.side_effect = [first, install_ok, retry_timeout]

    # Shared assertions for both branches.
    with caplog.at_level(
        logging.WARNING, logger="mcp_tools_py.code_checker_pytest.runners"
    ):
        with pytest.raises(exc_cls) as excinfo:
            run_tests("/test/project", "tests", python_executable=sys.executable)

    msg = str(excinfo.value)
    assert msg_substring in msg
    assert "STDERR_MARKER_abc" in msg
    assert "STDOUT_MARKER_xyz" in msg

    matching = [
        r
        for r in caplog.records
        if r.levelno == logging.WARNING
        and log_substring in r.getMessage().lower()
    ]
    assert matching, f"expected WARNING for branch {second_kind}"
```

The exact `side_effect` sequence depends on what triggers the install-retry block in the current `run_tests` implementation — verify against the actual control flow when writing the test.

Add `import logging` to the test file if not already imported. Existing imports (`pytest`, `MagicMock`, `patch`, `sys`, `run_tests`) cover the rest.

---

## HOW (integration points)

- **No new imports** in `runners.py`. `logger` (already bound near line 44) and `_build_error_detail` (line 26) are already in scope.
- **Possible new import** in `test_runners.py`: `import logging` (only if not already present). Everything else is reused.
- **No public API change**: exception types (`RuntimeError` / `ValueError` / `TimeoutError`) and labels (`"Internal Error"` / `"Usage Error"` / `"Plugin Error"` / `"Failed to install …"` / `"Timed out while retrying …"`) are preserved. The trailing `"Suggestion: …"` text is replaced with the `stderr:`/`stdout:` snippet for the three returncode branches; the install-failure, retry-timeout, and no-report-file branches gain the same trailing snippet appended to their existing message.
- **No config / decorator / dependency changes.**

---

## ALGORITHM

**Per `print` → `logger.warning` conversion**: same message text, same level semantics; only the sink changes (stdout → stderr-bound log handler).

**Per error-exit branch (3, 4, >5)**:

```
on returncode in {3, 4, >5}:
    log combined stdout+stderr at WARNING level (server-side visibility, no stdout pollution)
    detail = _build_error_detail(stdout, stderr)   # truncated, prefixed " stderr: …  stdout: …"
    raise <Exc>(f"<Label>: {error_context.exit_code_meaning}.{detail}")
```

`_build_error_detail` (already in the file, lines 26–41) handles empty output, applies `truncate_stderr()` defaults, and produces the exact format expected.

---

## DATA

### Return values
- **Unchanged.** Branches that previously raised still raise; branches that previously logged-and-continued still log-and-continue (now via `logger.warning` instead of `print` + later `logger`).

### Exception message structure (3 / 4 / >5 branches)
```
"<Label>: <exit_code_meaning>. stderr: <truncated stderr> stdout: <truncated stdout>"
```
- `<Label>` ∈ {`Internal Error`, `Usage Error`, `Plugin Error`}.
- `<exit_code_meaning>` from `error_context.exit_code_meaning` (set by `create_error_context` in `utils.py`).
- `stderr` / `stdout` segments produced by `_build_error_detail` (each prefixed with leading space; either may be empty).

### Log records
- Logger: `mcp_tools_py.code_checker_pytest.runners` (already-bound `logger`).
- Level: `WARNING`.
- New records emitted at every former `print()` site inside `run_tests`.

---

## Quality gates (must all pass before commit)

```python
mcp__mcp-tools-py__run_pylint_check()
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])
mcp__mcp-tools-py__run_mypy_check()
```

Then `mcp__mcp-tools-py__run_format_code()` → `git add` (the two modified files) → `git commit`.

---

## LLM prompt for this step

> Implement Step 1 from `pr_info/steps/step_1.md` (refer to `pr_info/steps/summary.md` for context).
>
> Follow TDD: first add parametrized test coverage to `tests/test_code_checker/test_runners.py` (uses `caplog`) for **all eight raising error paths** in `run_tests`: lines 217 (execution-error), 223 (subprocess timeout), 271 (install fail), 289 (retry timeout), 337 (rc=3), 343 (rc=4), 355 (rc>5), and 384 (no-report-file). Each case asserts the raised exception text carries `STDOUT_MARKER` and `STDERR_MARKER`, plus a matching `WARNING` log record where one is emitted. Suggested split into two parametrized tests when the install/retry cases need divergent `execute_command` `side_effect` setup (`test_run_tests_surfaces_pytest_output_on_error_exit_codes` for 217/223/337/343/355/384, `test_run_tests_surfaces_pytest_output_on_install_and_retry_failures` for 271/289). Place them right after `test_run_tests_default_test_folder_appended`. The no-report-file case needs `os.path.isfile` patched to return `False`. Confirm failure against current code.
>
> Then in `src/mcp_tools_py/code_checker_pytest/runners.py`, replace **every** `print()` call inside `run_tests` — pytest-output / failure-diagnostic sites (~230 timeout-warning, 271 install-fail, 289 retry-timeout, 304 install/retry handler, ~363 no-report dump, 416–418 outer handler) become `logger.warning(...)`; operational sites (~210 command echo, ~221 return-code echo, ~247 plugin-not-found, ~278 installed-retrying) become `logger.debug(...)`; and **delete** the line-309 `print("No tests found, raising specific exception")` (tautological with the next-line `raise ValueError(...)`). Additionally, append `_build_error_detail(...)` inline to the raised exception messages at:
> - line 217 — `_build_error_detail(subprocess_result.stdout, subprocess_result.stderr)` on the `RuntimeError(execution_error)` (verified: `execution_error` is a separate string field — does not contain stdout/stderr),
> - line 223 — `_build_error_detail(subprocess_result.stdout, subprocess_result.stderr)` on the `TimeoutError`,
> - line 271 — `_build_error_detail(install_result.stdout, install_result.stderr)` on the `RuntimeError`,
> - line 289 — `_build_error_detail(retry_result.stdout, retry_result.stderr)` on the `TimeoutError`,
> - lines 337/343/355 — `_build_error_detail(output, error_output)` on the `RuntimeError`/`ValueError`/`RuntimeError`, and drop the `if error_context else <fallback>` ternaries (`error_context` is guaranteed non-None at these branches per lines 317–320),
> - line 384 — replace the `if stderr.strip(): base_msg += " stderr: …"` block with `base_msg += _build_error_detail(output, error_output)`.
>
> Match the inline pattern already used at line 311. Do **not** introduce a new helper / abstraction. Reuse existing helpers — do not reimplement.
>
> Run all three quality gates (pylint, pytest with `-n auto -m "not integration"`, mypy) and confirm green. Run `mcp__mcp-tools-py__run_format_code`, stage the two modified files, and produce one commit with a message describing the bug fix and referencing issue #187.
>
> Do not modify any other checker runners (pylint, mypy, ruff, etc.) — that audit is out of scope per the issue.
