# Step 1: Update file_utils shim and swap pytest/utils.py consumer

**Summary:** [summary.md](./summary.md)

## Goal

Replace the hand-written `read_file` in `utils/file_utils.py` with a re-export shim from `mcp_coder_utils.fs`, and replace the duplicate copy in `code_checker_pytest/utils.py` with an import from the shim.

## Test first

### WHERE
`tests/test_shim_reexports.py` (new file)

### WHAT
Test that `mcp_tools_py.utils.file_utils.read_file` is the same object as `mcp_coder_utils.fs.read_file`:

```python
def test_file_utils_read_file_is_reexport():
    from mcp_tools_py.utils.file_utils import read_file
    from mcp_coder_utils.fs import read_file as upstream
    assert read_file is upstream
```

Test that `mcp_tools_py.code_checker_pytest.utils.read_file` works (reads a temp file):

```python
def test_pytest_utils_read_file(tmp_path):
    p = tmp_path / "hello.txt"
    p.write_text("hello", encoding="utf-8")
    from mcp_tools_py.code_checker_pytest.utils import read_file
    assert read_file(str(p)) == "hello"
```

## Implementation

### File 1: `src/mcp_tools_py/utils/file_utils.py`

**WHAT:** Replace the hand-written function body with a re-export shim.

**HOW:**
```python
"""File operation utilities — thin re-export shim.

All functionality is provided by mcp_coder_utils.fs.
This module re-exports the public API for backward compatibility.
"""

from mcp_coder_utils.fs import read_file  # noqa: F401

__all__ = ["read_file"]
```

**DATA:** `read_file(file_path: str | Path, encoding: str | None = "utf-8") -> str` — same signature, backward compatible.

### File 2: `src/mcp_tools_py/utils/__init__.py`

**WHAT:** No change needed — already re-exports `read_file` from `.file_utils`.

### File 3: `src/mcp_tools_py/code_checker_pytest/utils.py`

**WHAT:** Delete the local `read_file` function (lines 104-121), replace with import from the shim.

**HOW:** Add at top of file:
```python
from mcp_tools_py.utils.file_utils import read_file
```

Remove the `read_file` function definition. All existing callers (e.g. `runners.py` doing `from mcp_tools_py.code_checker_pytest.utils import read_file`) continue to work because the name is still exported from the same module.

**ALGORITHM:**
```
1. Add import of read_file from utils.file_utils
2. Delete the local read_file function definition
3. Verify read_file is still importable from code_checker_pytest.utils
```

## Verify

Run pylint, pytest, mypy — all must pass.

## LLM Prompt

```
Read pr_info/steps/summary.md and pr_info/steps/step_1.md.
Implement step 1: update the file_utils.py shim to re-export from mcp_coder_utils.fs,
replace the local read_file copy in code_checker_pytest/utils.py with an import from the shim,
and add the shim re-export test. Run all code quality checks after.
```
