# Step 4: Integration Tests

**Commit:** `test: add end-to-end refactoring integration tests (#108)`

**Context:** See `pr_info/steps/summary.md` for full issue context. Steps 1-3 must be completed first.

**Goal:** Add end-to-end integration tests that exercise the full workflow: discover symbols, check references, move/rename, verify imports updated correctly. Also test MCP tool registration end-to-end.

---

## LLM Prompt

> **Task:** Implement Step 4 of Issue #108 (Add Python refactoring tools).
> Read `pr_info/steps/summary.md` for full context, then follow `pr_info/steps/step_4.md` exactly.
>
> Add end-to-end integration tests for the refactoring tools.
> Test the full workflow: discover → analyze → refactor → verify.
> All checks must pass. This is the final step.

---

## Part A: RefactoringTools registration tests

### WHERE
- `tests/test_refactoring/test_refactoring_tools.py` (new)

### WHAT
```python
def test_refactoring_tools_registers_five_tools() -> None:
    """RefactoringTools registers all 5 tools on an MCP server."""
    # Create RefactoringTools with a tmp_path project_dir
    # Create a mock/minimal FastMCP
    # Call register()
    # Verify 5 tools registered: list_symbols, find_references, move_symbol, rename, move_module

def test_refactoring_tools_use_relative_paths(tmp_path: Path) -> None:
    """All tool outputs use relative paths, never absolute."""
    # Create sample project, call list_symbols and find_references through registration
    # Assert no absolute paths in output
```

---

## Part B: End-to-end workflow tests

### WHERE
- `tests/test_refactoring/test_integration.py` (new)

### WHAT
```python
@pytest.fixture
def multi_module_project(tmp_path: Path) -> Path:
    """Create a realistic multi-module project for integration testing.

    Structure:
        myproject/
        ├── __init__.py
        ├── models.py        # defines: User, Address, validate_email
        ├── services.py      # imports and uses User, validate_email from models
        └── utils.py          # imports Address from models
    """
    ...
    return tmp_path

def test_full_workflow_split_large_file(multi_module_project: Path) -> None:
    """End-to-end: discover symbols, move one to new module, verify imports."""
    # 1. list_symbols on models.py → should show User, Address, validate_email
    # 2. find_references for validate_email → should show models.py, services.py
    # 3. move_symbol validate_email from models.py to validation.py (dry_run=True)
    #    → verify [DRY RUN] output, files unchanged
    # 4. move_symbol validate_email from models.py to validation.py (dry_run=False)
    #    → verify validation.py exists and defines validate_email
    #    → verify models.py no longer defines validate_email
    #    → verify services.py imports from validation, not models
    #    → verify utils.py unchanged (it imports Address, not validate_email)

def test_rename_then_verify_references(multi_module_project: Path) -> None:
    """End-to-end: rename a class, verify all references updated."""
    # 1. find_references for User → should show models.py, services.py
    # 2. rename User to AppUser (dry_run=True) → verify preview
    # 3. rename User to AppUser (dry_run=False)
    #    → verify models.py defines AppUser, not User
    #    → verify services.py references AppUser

def test_move_module_then_verify_imports(multi_module_project: Path) -> None:
    """End-to-end: move a module to a subpackage, verify imports updated."""
    # 1. move_module utils.py to subpkg/ (dry_run=False)
    #    → verify subpkg/utils.py exists
    #    → verify models.py imports unaffected (utils imports from models, not vice versa)
```

### HOW
- Use `tmp_path` fixture for isolated file system
- Call `jedi_tools` and `rope_tools` functions directly (not through MCP transport)
- Read files after refactoring to verify content changes
- All paths relative to `tmp_path` project root

---

## Part C: Pytest marker for refactoring tests

### WHERE
- `pyproject.toml` (modify)

### WHAT — add marker
```toml
[tool.pytest.ini_options]
markers = [
    # ... existing markers ...
    "refactoring_integration: Refactoring integration tests (rope + jedi)",
]
```

### HOW
- Mark integration tests with `@pytest.mark.refactoring_integration`
- These tests create temp projects and exercise rope/jedi, so they're slower than pure unit tests
- Can be excluded from fast test runs: `-m "not refactoring_integration"`

---

## Verification Checklist

1. All integration tests pass
2. All unit tests from steps 1-3 still pass
3. All existing tests still pass
4. pylint, mypy pass on all new test files
5. Architecture checks (tach, import-linter) pass
6. Run full test suite: `pytest -n auto` — all green
