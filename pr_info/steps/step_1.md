# Step 1: Model + Path Detection in `sanitize_extra_args()`

> **Context**: See `pr_info/steps/summary.md` for full issue context and architectural overview.

## LLM Prompt

```
Implement Step 1 of Issue #111 (see pr_info/steps/summary.md for context).

Add path detection to sanitize_extra_args() so it sets has_path_args=True when
extra_args contains valid test paths. Follow TDD: write tests first, then implement.

Files to modify:
1. src/mcp_tools_py/code_checker_pytest/models.py — add has_path_args field
2. tests/test_code_checker_pytest/test_extra_args.py — add new path detection tests
3. src/mcp_tools_py/code_checker_pytest/utils.py — implement path detection

Run all three code quality checks (pylint, pytest, mypy) after changes.
Commit when all checks pass.
```

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/code_checker_pytest/models.py` | Modify |
| `src/mcp_tools_py/code_checker_pytest/utils.py` | Modify |
| `tests/test_code_checker_pytest/test_extra_args.py` | Modify |

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

### test_extra_args.py — New test cases

New test class `TestSanitizeExtraArgsPathDetection` with tests for:
- Existing file path sets `has_path_args=True`
- Existing directory path sets `has_path_args=True`
- Node ID (`tests/test_file.py::test_func`) with existing file sets `has_path_args=True`
- Non-existent path keeps `has_path_args=False`, adds note
- Absolute path keeps `has_path_args=False`, adds note
- Mixed args (flags + paths) correctly detects paths
- Empty `project_dir` (default) keeps `has_path_args=False`
- Existing tests still pass unchanged (defaults handle backward compat)

## HOW

### Integration Points
- `sanitize_extra_args()` is called from `checker_tools.py` (wired in Step 2)
- `SanitizedArgs.has_path_args` is read in `checker_tools.py` (wired in Step 2)
- No import changes needed — `os` already importable in utils.py

### Imports to Add in utils.py
```python
import os
```

## ALGORITHM — Path detection loop (in `sanitize_extra_args`, after existing stripping)

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

## DATA

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
    has_path_args=True,   # NEW
)
```

## Commit Message
```
fix(pytest): add path detection to sanitize_extra_args (#111)

Add has_path_args field to SanitizedArgs and path detection logic to
sanitize_extra_args(). When extra_args contains valid test paths (files,
directories, or node IDs), has_path_args is set to True. This will be
used in Step 2 to skip appending the default test folder.
```
