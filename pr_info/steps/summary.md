# Issue #111: run_pytest_check extra_args path filter does not restrict test collection

## Summary

When passing a specific test path via `extra_args`, `run_pytest_check` ignores the path and collects **all** tests. The root cause: `run_tests()` unconditionally appends the default `test_folder` ("tests") to the pytest command. Since pytest unions all positional path arguments, the broad `tests/` directory always dominates.

## Approach

Add path detection to `sanitize_extra_args()` so that when the user provides explicit test paths, the default `test_folder` is not appended. This is the minimal change that fixes the bug while keeping the existing pipeline intact.

## Architectural / Design Changes

### Data Model Change
- `SanitizedArgs` gains one field: `has_path_args: bool = False`
- Default `False` preserves backward compatibility — no existing callers break

### Logic Change in `sanitize_extra_args()` (utils.py)
- New `project_dir: str = ""` parameter for resolving relative paths
- After existing bare `tests`/`tests/` stripping, remaining non-flag args are checked:
  - Node IDs (`::` in arg): file part checked relative to `project_dir`
  - Plain paths: checked as file/dir relative to `project_dir`
  - Absolute paths: not counted as path args (security)
  - Non-existent paths: treated as regular pytest args (safe fallback)
- If any valid path detected → `has_path_args = True`

### Conditional Test Folder Append (runners.py)
- New `skip_default_test_folder: bool = False` parameter on `run_tests()` and `check_code_with_pytest()`
- Single guard: `if not skip_default_test_folder: command.append(...)`

### Wiring (checker_tools.py)
- Pass `project_dir` to `sanitize_extra_args()`
- Pass `skip_default_test_folder=sanitized.has_path_args` to `check_code_with_pytest()`

### Design Decisions

| Decision | Rationale |
|----------|-----------|
| All new params have defaults | Backward compatible — existing callers/tests untouched |
| Path detection in sanitizer, not runner | Single responsibility — sanitizer already inspects args |
| Bare `tests` stripped before path detection | Avoids false positive on the default folder |
| Non-existent paths = non-path args | Safe fallback, user gets a note for debugging |
| Absolute paths ignored for detection | Prevents path traversal outside project |

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/code_checker_pytest/models.py` | Add `has_path_args: bool = False` to `SanitizedArgs` |
| `src/mcp_tools_py/code_checker_pytest/utils.py` | Add `project_dir` param and path detection to `sanitize_extra_args()` |
| `src/mcp_tools_py/code_checker_pytest/runners.py` | Add `skip_default_test_folder` param, conditional append |
| `src/mcp_tools_py/checker_tools.py` | Wire `project_dir` and `skip_default_test_folder` |
| `tests/test_code_checker_pytest/test_extra_args.py` | New tests for path detection |
| `tests/test_code_checker/test_runners.py` | New tests for conditional test folder skip + integration test |

## No New Files Created

All changes are modifications to existing files.

## Implementation Steps

- **Step 1**: Path detection in `sanitize_extra_args()`, conditional test folder append in runners, wiring in checker_tools, and all tests (single commit)
