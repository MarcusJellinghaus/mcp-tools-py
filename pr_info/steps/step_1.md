# Step 1: Path Detection + Conditional Test Folder Append

> **Context**: See `pr_info/steps/summary.md` for full issue context and architectural overview.

## LLM Prompt

```
Implement the fix for Issue #111 (see pr_info/steps/summary.md for context).

Add path detection to sanitize_extra_args() and wire it through to runners.py
so the default test folder is skipped when extra_args contains valid paths.
Follow TDD: write tests first, then implement.

Files to modify:
1. src/mcp_tools_py/code_checker_pytest/models.py — add has_path_args field
2. tests/test_code_checker_pytest/test_extra_args.py — add path detection tests
3. src/mcp_tools_py/code_checker_pytest/utils.py — implement path detection
4. tests/test_code_checker/test_runners.py — add skip_default_test_folder tests + integration test
5. src/mcp_tools_py/code_checker_pytest/runners.py — add skip_default_test_folder param
6. src/mcp_tools_py/checker_tools.py — pass project_dir and skip_default_test_folder

Run all three code quality checks (pylint, pytest, mypy) after changes.
Commit when all checks pass.
```

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/code_checker_pytest/models.py` | Modify |
| `src/mcp_tools_py/code_checker_pytest/utils.py` | Modify |
| `src/mcp_tools_py/code_checker_pytest/runners.py` | Modify |
| `src/mcp_tools_py/checker_tools.py` | Modify |
| `tests/test_code_checker_pytest/test_extra_args.py` | Modify |
| `tests/test_code_checker/test_runners.py` | Modify |

## WHAT

### models.py — Add field to `SanitizedArgs`

```python
@dataclass
class SanitizedArgs:
    cleaned_args: List[str]
    verbosity: int
    notes: List[str]
    has_path_args: bool = False  # NEW — True when extra_args contains valid test paths
```

### utils.py — Enhanced `sanitize_extra_args()`

```python
def sanitize_extra_args(
    extra_args: Optional[List[str]],
    markers: Optional[List[str]],
    project_dir: str = "",          # NEW parameter
) -> SanitizedArgs:
```

### runners.py — Add `skip_default_test_folder` parameter

Both functions get the new parameter:

```python
def run_tests(
    project_dir: str,
    test_folder: str,
    python_executable: str,
    ...,
    skip_default_test_folder: bool = False,  # NEW
) -> PytestReport:

def check_code_with_pytest(
    project_dir: str,
    python_executable: str,
    ...,
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

### test_extra_args.py — Path detection tests

New test class `TestSanitizeExtraArgsPathDetection` with tests for:
- Existing file path sets `has_path_args=True`
- Existing directory path sets `has_path_args=True`
- Node ID (`tests/test_file.py::test_func`) with existing file sets `has_path_args=True`
- Non-existent path keeps `has_path_args=False`, adds note
- Absolute path keeps `has_path_args=False`, adds note
- Mixed args (flags + paths) correctly detects paths
- Empty `project_dir` (default) keeps `has_path_args=False`
- Existing tests still pass unchanged (defaults handle backward compat)

### test_runners.py — Runner tests + integration test

Unit tests:
- `test_run_tests_skip_default_test_folder`: When `skip_default_test_folder=True`, the command does NOT contain the test_folder path
- `test_run_tests_default_test_folder_appended`: Default behavior unchanged (test_folder IS appended)
- Update `test_check_code_with_pytest_with_custom_parameters` mock assertion to include `skip_default_test_folder`

Integration test for full command construction flow:
- `test_path_args_skip_default_folder_integration`: Mock `execute_command` in runners.py, call `check_code_with_pytest()` with a specific test path in `extra_args` and `skip_default_test_folder=True`, assert the built pytest command contains the user's path but does NOT contain the default `tests/` folder path
- Also test the inverse: without path args (`skip_default_test_folder=False`), the default test folder IS in the command

## HOW

### Path detection loop (in `sanitize_extra_args`, after existing stripping)

```
has_path_args = False
for each arg in cleaned_args:
    if arg starts with "-": skip (it's a flag)
    if os.path.isabs(arg): add note "absolute path ignored", skip
    # Handle node IDs: "path/to/file.py::test_name"
    file_part = arg.split("::", 1)[0] if "::" in arg else arg
    full_path = os.path.join(project_dir, file_part)
    if project_dir and os.path.exists(full_path):
        has_path_args = True
        add note "Path argument detected; default test folder not appended."
    elif project_dir and not os.path.exists(full_path):
        add note "Path 'X' not found relative to project_dir"
```

**Key**: path detection runs on `cleaned_args` (after bare `tests`/`tests/` already stripped), so the default folder is never mistaken for a user-specified path.

### Conditional append (in `run_tests`)

Replace:
```python
command.append(os.path.join(project_dir, test_folder))
```

With:
```python
if not skip_default_test_folder:
    command.append(os.path.join(project_dir, test_folder))
```

### Forward param in `check_code_with_pytest()`

Pass `skip_default_test_folder` to `run_tests()`:
```python
test_results = run_tests(
    ...,
    skip_default_test_folder=skip_default_test_folder,
)
```

### Wire in checker_tools.py

```python
sanitized = sanitize_extra_args(extra_args, markers, project_dir=str(self._server.project_dir))
# ...
test_results = check_code_with_pytest(
    ...,
    skip_default_test_folder=sanitized.has_path_args,
)
```

### Imports to add in utils.py

```python
import os
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

### Input (unchanged)
- `extra_args: Optional[List[str]]`
- `markers: Optional[List[str]]`
- `project_dir: str = ""` (NEW)

### Output — `SanitizedArgs`
```python
SanitizedArgs(
    cleaned_args=["-x", "tests/test_file.py::test_func"],
    verbosity=2,
    notes=["Path argument 'tests/test_file.py::test_func' detected; default test folder not appended."],
    has_path_args=True,
)
```

### Existing test expectations
- `test_check_code_with_pytest_with_custom_parameters`: Currently asserts exact positional args to `mock_run_tests`. This test needs updating to include the new `skip_default_test_folder` kwarg in the expected call. Use `skip_default_test_folder=False` since that test doesn't pass paths.

## Commit Message
```
fix(pytest): skip default test folder when extra_args contains paths (#111)

Add path detection to sanitize_extra_args() and wire through to
run_tests() via skip_default_test_folder. When extra_args contains valid
test paths, the default test_folder is not appended to the pytest
command, allowing path-based filtering to work as expected.
```
