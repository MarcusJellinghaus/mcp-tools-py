# Step 4: Cleanup — remove dead code and fragile tests

**Summary**: See `pr_info/steps/summary.md` for full context (Issue #112).

Remove code that became dead after Step 3 (subprocess replacement) and tests
that break when the manual test plan mutates `sample_project/`.

## WHERE: Files to modify

| File | Action |
|------|--------|
| `tests/test_refactoring/test_integration.py` | Remove 3 "real project dir" tests |
| `src/mcp_tools_py/refactoring/rope_tools.py` | Remove unused import and function |

## WHAT: Specific changes

### 1. Remove "real project dir" integration tests

**File**: `tests/test_refactoring/test_integration.py`

Remove these 3 test functions and the `_REAL_PROJECT_DIR` constant:

```python
# Remove this constant:
_REAL_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent

# Remove these 3 functions:
def test_rename_symbol_real_project_does_not_hang()
def test_move_symbol_real_project_does_not_hang()
def test_move_module_real_project_does_not_hang()
```

Also remove the TODO comment block above them.

**Why**: These tests reference files in `tests/mcp_tools_py_manual/sample_project/`
by hardcoded name (e.g., `MAX_NAME_LENGTH`, `format_user`). When Phase 3 of the
manual test plan mutates those files, these integration tests fail. The
`tmp_path`-based hang-regression tests (`test_*_does_not_hang` using the
`multi_module_project` fixture) already cover the same scenario in a properly
isolated way.

**Keep**: All `tmp_path`-based tests remain (they use the `multi_module_project`
fixture and are fully isolated).

### 2. Remove unused `import rope.base.project`

**File**: `src/mcp_tools_py/refactoring/rope_tools.py`

Remove this line:
```python
import rope.base.project  # pylint: disable=import-error
```

The module is already imported via:
```python
from rope.base.project import Project  # pylint: disable=import-error
```

The bare `import rope.base.project` is not referenced anywhere.

### 3. Remove unused `apply_gitignore_filter()`

**File**: `src/mcp_tools_py/refactoring/rope_tools.py`

Remove the entire `apply_gitignore_filter()` function (~25 lines). It was copied
from `p_workspace` alongside `read_gitignore_rules()` but is never called in
this file. Only `read_gitignore_rules()` is used (by `_build_ignored_resources()`).

**Verify**: Search the codebase for `apply_gitignore_filter` — it should only
appear in `rope_tools.py` (definition) and nowhere else as an import or call.

## VERIFY

After all changes:

1. `git diff` — confirm only the expected deletions
2. Run quality checks: pylint, pytest (`-n auto -m "not integration"`), mypy
3. Run integration tests specifically: `pytest tests/test_refactoring/ -v`
4. Confirm no remaining references to removed code:
   - `grep -r "apply_gitignore_filter" src/ tests/`
   - `grep -r "_REAL_PROJECT_DIR" src/ tests/`

## Commit message
```
refactor(refactoring): remove dead code and fragile real-project-dir tests
```
