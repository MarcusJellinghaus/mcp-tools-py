# Step 2 — Preserve `INTERNALERROR>` Lines on Exit Code 3

## LLM Prompt

> Read `pr_info/steps/summary.md` for issue context and `pr_info/steps/step_2.md` (this file) for the specific work. Implement Step 2 only: when pytest exits with code 3, preserve `INTERNALERROR>` lines verbatim and untruncated in the raised `RuntimeError`. Follow TDD — add the regression test first (it should fail with truncation), then change the exit-3 branch in `runners.py` so the test passes. Touch only the exit-code-3 branch (lines 356-363) — leave `_build_error_detail` and all other branches alone. Run `mcp__tools-py__run_pylint_check`, `mcp__tools-py__run_pytest_check` (with the fast-unit-test marker exclusion from `.claude/CLAUDE.md`), and `mcp__tools-py__run_mypy_check`. All three must pass before the commit.

## Goal

Surface the pytest `INTERNALERROR>` block — the only output that identifies the crashing test — in the `RuntimeError` raised on exit code 3, bypassing the 500-char `truncate_stderr` cap for those lines.

## WHERE

**Source file (modify):**

- `src/mcp_tools_py/code_checker_pytest/runners.py` — exit-code-3 branch at lines 356-363 (function `run_tests`).

**Test file (modify):**

- `tests/test_code_checker/test_runners.py` — extend the parametrized exit-code error test (currently lines 394-403 for `internal_error_3`), or add a sibling test that uses a realistic multi-line `INTERNALERROR>` block long enough to exceed the 500-char truncation cap.

## WHAT

### `src/mcp_tools_py/code_checker_pytest/runners.py`

Replace the body of the `elif process.returncode == 3:` branch only:

```python
elif process.returncode == 3:
    assert error_context is not None
    logger.warning("Pytest internal error (exit 3): %s", combined_output)
    internal_lines = "\n".join(
        line for line in combined_output.splitlines()
        if line.startswith("INTERNALERROR>")
    )
    prefix = f"{internal_lines}\n" if internal_lines else ""
    raise RuntimeError(
        f"{prefix}Internal Error: {error_context.exit_code_meaning}."
        f"{_build_error_detail(output, error_output)}"
    )
```

- No new imports.
- No changes to `_build_error_detail`.
- No changes to other `elif` branches (exit 4, exit >5, timeout, etc.).
- The `logger.warning` call is unchanged.

## HOW

- Pure additive change inside one branch; behaviour is identical to today when no `INTERNALERROR>` lines are present (`prefix == ""`).
- Lines joined by `\n`, no extra header — pytest's own `INTERNALERROR>` prefix is self-labeling.

## ALGORITHM

```
on exit code 3:
    scan combined_output line by line
    keep lines that start with "INTERNALERROR>"
    if any kept: prefix = "\n".join(kept) + "\n", else prefix = ""
    raise RuntimeError(prefix + "Internal Error: <meaning>." + _build_error_detail(...))
```

## DATA

- Existing exception type unchanged: `RuntimeError`.
- New message shape (when INTERNALERROR present):
  ```
  INTERNALERROR> File ".../dsession.py", line 217, in worker_workerfinished
  INTERNALERROR>     assert not crashitem, (crashitem, node)
  INTERNALERROR> AssertionError: (...)
  Internal Error: Internal pytest error. stderr: ... stdout: ...
  ```
- Message shape when no `INTERNALERROR>` lines (regression-safe): identical to today.

## Test Changes (TDD — Write These First)

### `tests/test_code_checker/test_runners.py`

Add a new test (sibling of the parametrized exit-code test, not part of the parametrize block — the realistic payload would inflate every parametrized case):

```python
@patch("mcp_tools_py.code_checker_pytest.runners.execute_command")
def test_internal_error_3_preserves_internalerror_block_untruncated(
    mock_execute: MagicMock,
) -> None:
    """Exit-3: INTERNALERROR> lines must survive the 500-char truncate_stderr cap."""
    # Build a payload whose INTERNALERROR section, when concatenated with
    # surrounding stderr noise, comfortably exceeds MAX_STDERR_IN_ERROR (500).
    noise = "X" * 600
    internalerror_block = "\n".join([
        "INTERNALERROR> Traceback (most recent call last):",
        "INTERNALERROR>   File \".../xdist/dsession.py\", line 217, in worker_workerfinished",
        "INTERNALERROR>     assert not crashitem, (crashitem, node)",
        "INTERNALERROR> AssertionError: ('tests/workflows/.../test_workflow.py::TestX::test_y', <WorkerController gw4>)",
    ])
    stderr_payload = f"{noise}\n{internalerror_block}\n{noise}"

    mock_execute.return_value = MagicMock(
        return_code=3,
        stdout="",
        stderr=stderr_payload,
        execution_error=None,
        timed_out=False,
    )

    with patch(
        "mcp_tools_py.code_checker_pytest.runners.os.path.isfile",
        return_value=True,
    ):
        with pytest.raises(RuntimeError) as excinfo:
            run_tests("/test/project", "tests", python_executable=sys.executable)

    msg = str(excinfo.value)
    # Each INTERNALERROR> line must appear verbatim in the message.
    for line in internalerror_block.splitlines():
        assert line in msg, f"missing INTERNALERROR line: {line!r}"
    # The existing label is still present.
    assert "Internal Error" in msg
```

This test fails on `main` because `truncate_stderr` cuts the stderr to 500 chars (the leading `noise` block alone exceeds that, so the `INTERNALERROR>` block is what gets cut). It passes after the implementation change.

## Quality Gates

```python
mcp__tools-py__run_pylint_check()
mcp__tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not git_integration and not claude_cli_integration and not claude_api_integration and not formatter_integration and not github_integration and not langchain_integration"])
mcp__tools-py__run_mypy_check()
```

## Commit Message Suggestion

```
Preserve INTERNALERROR> lines on pytest exit 3 (fixes #192 part 2)

When pytest exits with code 3 (internal error), prepend any
INTERNALERROR> lines verbatim and untruncated to the raised
RuntimeError, ahead of the existing truncated stderr/stdout snippet.
This surfaces the crashing test identity that the 500-char
truncate_stderr cap was previously discarding.

Scope: exit-code-3 branch only; other branches and _build_error_detail
are unchanged.
```
