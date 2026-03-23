# Step 2: Jedi Tools — list_symbols + find_references

**Commit:** `feat: add list_symbols and find_references tools (#108)`

**Context:** See `pr_info/steps/summary.md` for full issue context. Step 1 must be completed first (CheckerTools extracted, refactoring skeleton exists).

**Goal:** Implement the two read-only jedi-based tools (`list_symbols`, `find_references`), register them via `RefactoringTools`, and add tests.

---

## LLM Prompt

> **Task:** Implement Step 2 of Issue #108 (Add Python refactoring tools).
> Read `pr_info/steps/summary.md` for full context, then follow `pr_info/steps/step_2.md` exactly.
>
> Implement `list_symbols` and `find_references` in `jedi_tools.py`.
> Register both via `RefactoringTools` in `refactoring/__init__.py`.
> Write tests first (TDD). All checks must pass.

---

## Part A: Tests for jedi tools

### WHERE
- `tests/test_refactoring/test_jedi_tools.py` (new)

### WHAT
```python
import pytest
from pathlib import Path

from mcp_tools_py.refactoring.jedi_tools import list_symbols, find_references

# --- list_symbols tests ---

def test_list_symbols_functions(tmp_path: Path) -> None:
    """Lists top-level functions."""
    # Create a .py file with 2 functions → expect both returned

def test_list_symbols_classes(tmp_path: Path) -> None:
    """Lists top-level classes."""

def test_list_symbols_variables(tmp_path: Path) -> None:
    """Lists module-level variables (assigned names)."""

def test_list_symbols_ignores_nested(tmp_path: Path) -> None:
    """Does not list nested functions or class methods."""

def test_list_symbols_empty_file(tmp_path: Path) -> None:
    """Returns empty list for empty file."""

def test_list_symbols_nonexistent_file(tmp_path: Path) -> None:
    """Returns error string for missing file."""

def test_list_symbols_syntax_error(tmp_path: Path) -> None:
    """Returns error for file with syntax errors."""

# --- find_references tests ---

def test_find_references_function(tmp_path: Path) -> None:
    """Finds references to a function across multiple files."""
    # Create 2 files: one defines func, other imports and calls it

def test_find_references_class(tmp_path: Path) -> None:
    """Finds references to a class."""

def test_find_references_not_found(tmp_path: Path) -> None:
    """Returns error with available symbols when symbol not found."""

def test_find_references_import_usage(tmp_path: Path) -> None:
    """Finds import statements as references."""
```

### HOW
- Each test creates a temp project with `.py` files in `tmp_path`
- Calls the function directly (not through MCP) with paths relative to `tmp_path` as project root
- Asserts on returned strings (the formatted output)

---

## Part B: Implement jedi_tools.py

### WHERE
- `src/mcp_tools_py/refactoring/jedi_tools.py`

### WHAT
```python
"""Jedi-based symbol discovery and reference finding."""

from pathlib import Path
from typing import List


def list_symbols(project_dir: Path, file_path: str) -> str:
    """List all top-level symbols in a file.

    Args:
        project_dir: Absolute path to project root.
        file_path: File path relative to project root.

    Returns:
        Formatted string listing symbols, or error message.
    """
    ...


def find_references(project_dir: Path, file_path: str, symbol_name: str) -> str:
    """Find all references to a symbol across the project.

    Args:
        project_dir: Absolute path to project root.
        file_path: File path relative to project root.
        symbol_name: Name of the top-level symbol.

    Returns:
        Formatted string listing references, or error message.
    """
    ...
```

### ALGORITHM — list_symbols
```
1. Resolve absolute path = project_dir / file_path
2. Validate file exists, return error if not
3. source = read file content
4. script = jedi.Script(source=source, path=str(abs_path), project=jedi.Project(path=str(project_dir)))
5. names = script.get_names(all_scopes=False, definitions=True)
6. Filter to top-level only (names where .parent() is module)
7. Format each as "{type}: {name} (line {line})" and join with newlines
```

### ALGORITHM — find_references
```
1. Resolve absolute path, validate file exists
2. source = read file content
3. Find symbol's line/column in source (scan for top-level definition)
4. script = jedi.Script(source=source, path=str(abs_path), project=jedi.Project(path=str(project_dir)))
5. refs = script.get_references(line=line, column=col)
6. If no refs found, list available symbols as error hint
7. Format each ref as "{relative_path}:{line}: {description}" with paths relative to project_dir
```

### DATA — list_symbols return format
```
Symbols in src/example.py:
  function: my_function (line 5)
  class: MyClass (line 12)
  variable: MY_CONSTANT (line 1)
```

### DATA — find_references return format
```
References to 'my_function' (3 found):
  src/example.py:5: definition
  src/other.py:1: from src.example import my_function
  src/other.py:10: my_function()
```

### DATA — error format (symbol not found)
```
Symbol 'nonexistent' not found in src/example.py.
Available top-level symbols: my_function, MyClass, MY_CONSTANT
```

---

## Part C: Register in RefactoringTools

### WHERE
- `src/mcp_tools_py/refactoring/__init__.py`

### WHAT
```python
from mcp_tools_py.refactoring.jedi_tools import list_symbols, find_references
from mcp_tools_py.log_utils import log_function_call

class RefactoringTools:
    def __init__(self, project_dir: Path) -> None:
        self._project_dir = project_dir

    def register(self, mcp: "FastMCPProtocol") -> None:
        project_dir = self._project_dir

        @mcp.tool()
        @log_function_call
        def list_symbols(file: str) -> str:
            """List all top-level symbols (functions, classes, variables) in a Python file.

            Args:
                file: File path relative to project root.
            """
            return jedi_list_symbols(project_dir, file)

        @mcp.tool()
        @log_function_call
        def find_references(file: str, symbol_name: str) -> str:
            """Find all references to a symbol across the project.

            Args:
                file: File path relative to project root.
                symbol_name: Name of the top-level symbol to find.
            """
            return jedi_find_references(project_dir, file, symbol_name)
```

### HOW
- Import jedi_tools functions with aliases to avoid name collision with the MCP tool closures
- Decorate with `@mcp.tool()` and `@log_function_call` (same pattern as checker tools)
- Pass `self._project_dir` into the jedi functions

---

## Verification Checklist

1. `test_jedi_tools.py` tests pass
2. All existing tests still pass
3. pylint, mypy pass on new code
4. Tools appear when MCP server starts (manual or integration test)
