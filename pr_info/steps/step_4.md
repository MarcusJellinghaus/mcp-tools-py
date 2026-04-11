# Step 4: Subprocess Runner + Tests

> **Context**: Read `pr_info/steps/summary.md` first for full architecture overview.

## Prompt

```
Implement Step 4 of Issue #149 (bandit security linter).
Read pr_info/steps/summary.md for architecture context, then read this step file.

Create the runner module that builds the bandit CLI command, executes it via
subprocess, and returns a BanditResult. Follow the pattern from
code_checker_pylint/runners.py (returns Result container) combined with
code_checker_ruff/runners.py (command building pattern).

Reference tests/test_code_checker_ruff/test_runners.py for test structure.
Use tests/conftest.py make_command_result() for mocking.

After implementation, run all three code quality checks (pylint, pytest, mypy)
using MCP tools with the recommended fast unit test exclusions.
Commit: "feat(bandit): add subprocess runner with tests"
```

## WHERE

- **Create**: `src/mcp_tools_py/code_checker_bandit/runners.py`
- **Create**: `tests/test_code_checker_bandit/test_runners.py`
- **Modify**: `src/mcp_tools_py/code_checker_bandit/__init__.py` — add re-exports

## WHAT

### `runners.py`

```python
def _build_bandit_command(
    bandit_binary: str,
    target_directories: list[str],
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build the bandit CLI command list."""

@log_function_call
def run_bandit_check_impl(
    bandit_binary: str,
    project_dir: str,
    target_directories: list[str],
    extra_args: list[str] | None = None,
) -> BanditResult:
    """Run bandit and return structured result.

    Returns:
        BanditResult with parsed messages, file errors, or execution error.
    """
```

### ALGORITHM — `_build_bandit_command`

```
1. cmd = [bandit_binary, "-f", "json", "-r"]
2. cmd.extend(target_directories)
3. if extra_args: cmd.extend(extra_args)
4. return cmd
```

Note: `-r` is needed for recursive directory scanning. `-f json` sets JSON output format.

### ALGORITHM — `run_bandit_check_impl`

```
1. Validate project_dir exists (raise FileNotFoundError if not)
2. Build command via _build_bandit_command()
3. Execute via execute_command(cmd, cwd=project_dir)
4. If execution_error → return BanditResult(error=..., messages=[], errors=[])
5. If timed_out → return BanditResult(error="timed out", messages=[], errors=[])
6. If return_code == 2 → return BanditResult(error=stderr, messages=[], errors=[])
7. Parse stdout via parse_bandit_json_output(stdout, project_dir)
8. If parse_error → return BanditResult(error=parse_error, ...)
9. Return BanditResult(return_code, messages, errors, raw_output=stdout)
```

### DATA

**Return codes**: 0=no issues, 1=issues found, 2=error (same as ruff)

**`BanditResult`** fields populated by runner:
- `return_code`: from subprocess
- `messages`: from parser
- `errors`: from parser (file-level errors)
- `error`: set only on execution/parse failures
- `raw_output`: raw stdout for debugging

### Tests (`test_runners.py`)

| Test | What it validates |
|------|-------------------|
| `test_build_command_basic` | `[binary, "-f", "json", "-r", "src"]` |
| `test_build_command_with_extra_args` | Extra args appended at end |
| `test_build_command_multiple_directories` | Multiple dirs after `-r` |
| `test_no_issues` | return_code=0, empty JSON → BanditResult with empty messages |
| `test_with_issues` | return_code=1, valid JSON → BanditResult with messages |
| `test_error_exit_code_2` | return_code=2 → BanditResult with error from stderr |
| `test_execution_error` | execution_error set → BanditResult with error |
| `test_timeout` | timed_out=True → BanditResult with timeout error |
| `test_invalid_project_dir` | Non-existent dir → FileNotFoundError |

Use `@patch` on `execute_command` and `make_command_result()` from `tests/conftest.py`.
Build test JSON with a `_make_bandit_json()` helper similar to ruff's `_make_ruff_json()`.

## HOW

- Import `parse_bandit_json_output` from `.parsers`
- Import `BanditResult` from `.models`
- Import `execute_command` from `mcp_tools_py.utils.subprocess_runner`
- Import `log_function_call` from `mcp_tools_py.log_utils`
- Mock path: `"mcp_tools_py.code_checker_bandit.runners"`
