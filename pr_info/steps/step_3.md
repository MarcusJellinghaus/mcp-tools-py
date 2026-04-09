# Step 3: Runners (with tests)

> **Context**: See `pr_info/steps/summary.md` for the full plan. This is step 3 of 5.

## Goal

Create the runner functions that construct ruff CLI commands, execute them via `execute_command()`, and orchestrate the parse → report pipeline. Two functions: one for read-only check, one for fix (modifies files).

## LLM Prompt

```
Read pr_info/steps/summary.md for full context, then implement step 3.

Create runners.py in code_checker_ruff with run_ruff_check_impl() and
run_ruff_fix_impl(). Follow TDD: write tests in tests/test_code_checker_ruff/test_runners.py.
Mirror the vulture runner pattern (binary path, execute_command, return formatted output)
but with two functions. Mock execute_command in tests — do not call real ruff.

Key: ruff exit code 1 = violations found (not an error). Exit code 2 = actual error.
run_ruff_fix needs two subprocess calls: check first (to identify fixable files), then fix.

After implementation, run all three code quality checks (pylint, pytest, mypy).
Fix any issues before committing.
```

## WHERE

**Create:**
- `src/mcp_tools_py/code_checker_ruff/runners.py`
- `tests/test_code_checker_ruff/test_runners.py`

**Modify:**
- `src/mcp_tools_py/code_checker_ruff/__init__.py` — add re-exports for runner functions

## WHAT

### `runners.py`

```python
def _build_ruff_command(
    ruff_binary: str,
    subcommand: str,           # "check" or "check --fix"
    target_directories: list[str],
    select: list[str] | None = None,
    extra_args: list[str] | None = None,
    output_format: str = "json",
) -> list[str]:
    """Build the ruff CLI command list."""

def run_ruff_check_impl(
    ruff_binary: str,
    project_dir: str,
    target_directories: list[str],
    select: list[str] | None = None,
    extra_args: list[str] | None = None,
    max_issues: int = 1,
) -> str:
    """Run ruff check (read-only) and return formatted report.
    
    Returns:
        LLM-formatted report string, or "No issues found" message.
    """

def run_ruff_fix_impl(
    ruff_binary: str,
    project_dir: str,
    target_directories: list[str],
    select: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> str:
    """Run ruff check --fix (modifies files) and return fix report.
    
    Returns:
        Report with changed file list + remaining unfixed errors.
    """
```

## HOW

- `_build_ruff_command` constructs: `[binary, "check"] + ["--output-format", format] + ["--select", ",".join(select)] + extra_args + target_dirs`
- For `--fix` variant: insert `"--fix"` after `"check"`
- Uses `execute_command(command, cwd=project_dir, timeout_seconds=120)`
- Exit code handling: 0 = clean, 1 = violations found (parse output), 2 = real error (return error message)
- Handles `execution_error` and `timed_out` from `CommandResult`

## ALGORITHM — `run_ruff_check_impl`

```
1. cmd = _build_ruff_command(binary, "check", dirs, select, extra_args)
2. result = execute_command(cmd, cwd=project_dir)
3. if result.execution_error or result.timed_out: return error string
4. if result.return_code == 2: return "ruff error: " + stderr
5. messages, parse_error = parse_ruff_json_output(result.stdout, project_dir)
6. if parse_error: return parse_error
7. return format_ruff_check_report(messages, max_issues) or "No ruff issues found."
```

## ALGORITHM — `run_ruff_fix_impl`

```
1. check_cmd = _build_ruff_command(binary, "check", dirs, select, extra_args)
2. check_result = execute_command(check_cmd, cwd=project_dir)
3. pre_messages, _ = parse_ruff_json_output(check_result.stdout, project_dir)
4. changed_files = sorted({m.filename for m in pre_messages if m.fixable})
5. fix_cmd = _build_ruff_command(binary, "check", dirs, select, extra_args)  # same but with --fix
6.   → insert "--fix" into command
7. fix_result = execute_command(fix_cmd, cwd=project_dir)
8. remaining, _ = parse_ruff_json_output(fix_result.stdout, project_dir)
9. return format_ruff_fix_report(changed_files, remaining)
```

## DATA

**Input**: binary path, project_dir, target_directories, optional select/extra_args
**Output**: formatted string

`_build_ruff_command` example output:
```python
["/venv/bin/ruff", "check", "--output-format", "json", "--select", "D,DOC", "--preview", "src", "tests"]
```

## Tests — `test_runners.py`

All tests mock `execute_command` via `@patch`. Use `make_command_result` from `tests.conftest`.

Test cases:
1. `test_build_ruff_command_basic` — verify base command structure
2. `test_build_ruff_command_with_select` — verify `--select D,DOC` included
3. `test_build_ruff_command_with_extra_args` — verify extra args appended
4. `test_run_check_no_violations` — return code 0, empty output → "No ruff issues found."
5. `test_run_check_with_violations` — return code 1, JSON output → formatted report
6. `test_run_check_error_exit_code_2` — return code 2 → error message with stderr
7. `test_run_check_execution_error` — execution_error set → error string
8. `test_run_check_timeout` — timed_out=True → timeout message
9. `test_run_fix_applies_fixes` — mock two calls (check then fix), verify changed files in output
10. `test_run_fix_no_fixable_violations` — all violations unfixable → "no files modified"

## Commit

```
feat(ruff): add runners for ruff check and ruff fix

- _build_ruff_command() constructs CLI args with select/extra_args support
- run_ruff_check_impl() for read-only analysis with LLM-formatted output
- run_ruff_fix_impl() with pre-check for changed-file detection
- Exit code handling: 0=clean, 1=violations, 2=error
- Unit tests with mocked subprocess execution
```
