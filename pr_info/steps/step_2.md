# Step 2: Formatter runners (`black_runner.py` + `isort_runner.py`) + tests

> **Context**: See [summary.md](summary.md) for full issue context.

## Goal

Create the two runner functions that invoke black and isort as subprocesses. Each is a simple function that calls `execute_command()` and returns raw text output, capped at 200 lines.

## WHERE

| Action | File |
|--------|------|
| Create | `src/mcp_tools_py/formatter/__init__.py` (empty for now, just package marker) |
| Create | `src/mcp_tools_py/formatter/black_runner.py` |
| Create | `src/mcp_tools_py/formatter/isort_runner.py` |
| Create | `tests/test_black_runner.py` |
| Create | `tests/test_isort_runner.py` |

## WHAT — Function signatures

```python
# src/mcp_tools_py/formatter/black_runner.py

def run_black(
    python_executable: str,
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
) -> tuple[str, bool]:
    """Run black on target directories.

    Returns:
        Tuple of (output_text, success).
        success is True when return_code == 0.
    """
```

```python
# src/mcp_tools_py/formatter/isort_runner.py

def run_isort(
    python_executable: str,
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
) -> tuple[str, bool]:
    """Run isort on target directories.

    Returns:
        Tuple of (output_text, success).
        success is True when return_code == 0.
    """
```

## HOW — Integration

- Both import `execute_command` from `mcp_tools_py.utils.subprocess_runner`
- Command: `[python_executable, "-m", "<tool>"] + flags + target_dirs`
- `check_only=True` → `--check` for black, `--check-only` for isort
- Output = stdout + stderr combined, truncated to 200 lines

## ALGORITHM (pseudocode, same for both)

```
1. Build command: [python_executable, "-m", tool_name]
2. If check_only: append check flag (--check or --check-only)
3. Append target_dirs to command
4. result = execute_command(command, cwd=project_dir)
5. output = combine stdout + stderr, truncate to 200 lines
6. Return (output, result.return_code == 0)
```

## DATA — Truncation helper

```python
_MAX_LINES = 200

def _truncate_output(text: str) -> str:
    lines = text.splitlines()
    if len(lines) <= _MAX_LINES:
        return text
    truncated = lines[:_MAX_LINES]
    remaining = len(lines) - _MAX_LINES
    truncated.append(f"... (truncated, {remaining} more lines)")
    return "\n".join(truncated)
```

This helper can live in one of the runner files or as a shared `_truncate_output` in both (duplication of 6 lines is fine — no need for a separate module).

## TESTS — `tests/test_black_runner.py`

1. **test_run_black_success** — mock `execute_command` returning rc=0, verify output and `success=True`
2. **test_run_black_check_only_flag** — verify `--check` is in the command when `check_only=True`
3. **test_run_black_normal_mode_no_check_flag** — verify `--check` NOT in command when `check_only=False`
4. **test_run_black_failure** — mock rc=1, verify `success=False` and output preserved
5. **test_run_black_truncates_output** — mock stdout with 250 lines, verify capped at 200 + truncation notice
6. **test_run_black_combines_stdout_stderr** — mock both stdout and stderr, verify combined

## TESTS — `tests/test_isort_runner.py`

1. **test_run_isort_success** — mock `execute_command` returning rc=0, verify output and `success=True`
2. **test_run_isort_check_only_flag** — verify `--check-only` is in the command when `check_only=True`
3. **test_run_isort_normal_mode_no_check_flag** — verify `--check-only` NOT in command when `check_only=False`
4. **test_run_isort_failure** — mock rc=1, verify `success=False` and output preserved
5. **test_run_isort_truncates_output** — mock stdout with 250 lines, verify capped at 200 + truncation notice
6. **test_run_isort_combines_stdout_stderr** — mock both stdout and stderr, verify combined

## LLM Prompt

```
Implement Step 2 of issue #10 (see pr_info/steps/summary.md and pr_info/steps/step_2.md).

Create the formatter package with runner functions. Write tests first, then implement.

Files to create:
- src/mcp_tools_py/formatter/__init__.py (empty package init for now)
- src/mcp_tools_py/formatter/black_runner.py with run_black()
- src/mcp_tools_py/formatter/isort_runner.py with run_isort()
- tests/test_black_runner.py
- tests/test_isort_runner.py

Both runners follow the same pattern: build command, call execute_command(), combine and
truncate output, return (text, success). See existing checker code for style reference.

Run pylint, mypy, and pytest checks after implementation. Commit when all pass.
```
