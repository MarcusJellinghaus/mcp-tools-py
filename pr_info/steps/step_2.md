# Step 2: Conditional Test Folder Append + Wiring

> **Context**: See `pr_info/steps/summary.md` for full issue context and architectural overview.
> **Depends on**: Step 1 (path detection in `sanitize_extra_args()`)

## LLM Prompt

```
Implement Step 2 of Issue #111 (see pr_info/steps/summary.md for context).
Step 1 is already complete — sanitize_extra_args() now sets has_path_args=True
when valid paths are detected.

Wire the path detection through to runners.py so the default test folder is
skipped when has_path_args is True. Follow TDD: write tests first, then implement.

Files to modify:
1. tests/test_code_checker/test_runners.py — add test for skip_default_test_folder
2. src/mcp_tools_py/code_checker_pytest/runners.py — add skip_default_test_folder param
3. src/mcp_tools_py/checker_tools.py — pass project_dir and skip_default_test_folder

Run all three code quality checks (pylint, pytest, mypy) after changes.
Commit when all checks pass.
```

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/code_checker_pytest/runners.py` | Modify |
| `src/mcp_tools_py/checker_tools.py` | Modify |
| `tests/test_code_checker/test_runners.py` | Modify |

## WHAT

### runners.py — Add `skip_default_test_folder` parameter

Both functions get the new parameter:

```python
def run_tests(
    project_dir: str,
    test_folder: str,
    python_executable: str,
    ...
    skip_default_test_folder: bool = False,  # NEW
) -> PytestReport:

def check_code_with_pytest(
    project_dir: str,
    python_executable: str,
    ...
    skip_default_test_folder: bool = False,  # NEW
) -> Dict[str, Any]:
```

### checker_tools.py — Wire sanitized.has_path_args

```python
# In _register_pytest -> run_pytest_check:
sanitized = sanitize_extra_args(extra_args, markers, project_dir=str(self._server.project_dir))
# ...
test_results = check_code_with_pytest(
    ...,
    skip_default_test_folder=sanitized.has_path_args,
)
```

### test_runners.py — New tests

- `test_run_tests_skip_default_test_folder`: Verify that when `skip_default_test_folder=True`, the command does NOT contain the test_folder path
- `test_run_tests_default_test_folder_appended`: Verify default behavior unchanged (test_folder IS appended)
- Update `test_check_code_with_pytest_with_custom_parameters` mock assertion to include `skip_default_test_folder`

## HOW

### runners.py — Conditional append (the core fix)

In `run_tests()`, replace:
```python
# Add the test folder path
command.append(os.path.join(project_dir, test_folder))
```

With:
```python
# Add the test folder path (unless caller provided explicit paths)
if not skip_default_test_folder:
    command.append(os.path.join(project_dir, test_folder))
```

### runners.py — Forward param in `check_code_with_pytest()`

In `check_code_with_pytest()`, pass `skip_default_test_folder` to `run_tests()`:
```python
test_results = run_tests(
    project_dir,
    test_folder,
    python_executable,
    markers,
    verbosity,
    extra_args,
    env_vars,
    venv_path,
    keep_temp_files,
    timeout_seconds,
    skip_default_test_folder=skip_default_test_folder,  # NEW
)
```

### checker_tools.py — Pass project_dir to sanitizer

```python
sanitized = sanitize_extra_args(extra_args, markers, project_dir=str(self._server.project_dir))
```

And pass the flag to the runner:
```python
test_results = check_code_with_pytest(
    ...,
    skip_default_test_folder=sanitized.has_path_args,
)
```

## ALGORITHM — Conditional append (in `run_tests`)

```
# After building command with extra_args...
if not skip_default_test_folder:
    command.append(os.path.join(project_dir, test_folder))
# That's it — one guard, one line
```

## DATA

### New parameter flow
```
checker_tools.py:
  sanitized = sanitize_extra_args(extra_args, markers, project_dir=...)
  sanitized.has_path_args  →  skip_default_test_folder=True/False
    ↓
check_code_with_pytest(skip_default_test_folder=...)
    ↓
run_tests(skip_default_test_folder=...)
    ↓
if not skip_default_test_folder:
    command.append(test_folder)
```

### Existing test expectations
- `test_check_code_with_pytest_with_custom_parameters`: Currently asserts exact positional args to `mock_run_tests`. This test needs updating to include the new `skip_default_test_folder` kwarg in the expected call. Use `skip_default_test_folder=False` since that test doesn't pass paths.

## Commit Message
```
fix(pytest): skip default test folder when extra_args contains paths (#111)

Wire has_path_args from sanitize_extra_args() through to run_tests() via
the new skip_default_test_folder parameter. When True, the default
test_folder is not appended to the pytest command, allowing path-based
extra_args to restrict test collection as expected.
```
