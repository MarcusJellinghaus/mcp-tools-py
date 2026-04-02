# Step 1: Add `_strip_lint_imports_header()` helper, integrate into `run_lint_imports_check`, and add tests

> **Context:** See `pr_info/steps/summary.md` for full issue context (Issue #139).

## LLM Prompt

Implement the `_strip_lint_imports_header()` helper function, wire it into `run_lint_imports_check`, and add all unit tests. Write the tests first (TDD), then implement the function and integrate it. Run all code quality checks (pylint, pytest, mypy) and fix any issues before committing.

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/checker_tools.py` | Add `import re`, compiled regexes, module-level function `_strip_lint_imports_header`, and call it in `run_lint_imports_check` |
| `tests/test_checker_tools.py` | Add unit tests for the helper; update `test_lint_imports_success_returns_raw_output` with banner-containing mock input |

## WHAT

```python
# src/mcp_tools_py/checker_tools.py
import re

_BOX_DRAWING_OR_ARROWS = re.compile(r'[\u2500-\u257F▶◀▲▼]')
_ONLY_DASHES = re.compile(r'^-+$')

def _strip_lint_imports_header(raw: str) -> str:
    """Remove the import-linter ASCII art banner and dashed separators."""
```

## HOW

- Add `import re` to existing imports in `checker_tools.py`
- Add compiled regexes `_BOX_DRAWING_OR_ARROWS` and `_ONLY_DASHES` at module level
- Place `_strip_lint_imports_header` at module level, after imports and before the `CheckerTools` class
- In `_register_lint_imports` -> `run_lint_imports_check`, change the return from:
  ```python
  return output.strip() or "lint-imports produced no output."
  ```
  to:
  ```python
  output = _strip_lint_imports_header(output)
  return output or "lint-imports produced no output."
  ```
  Note: `_strip_lint_imports_header` already calls `.strip()` internally, so the explicit `.strip()` is no longer needed.

## ALGORITHM

```
_BOX_DRAWING_OR_ARROWS = re.compile(r'[\u2500-\u257F▶◀▲▼]')
_ONLY_DASHES = re.compile(r'^-+$')

def _strip_lint_imports_header(raw):
    lines = raw.splitlines()
    kept = [l for l in lines if not _BOX_DRAWING_OR_ARROWS.search(l) and not _ONLY_DASHES.match(l)]
    result = "\n".join(kept).strip()
    return result if result else raw
```

## DATA

- **Input:** `raw: str` — combined stdout+stderr from lint-imports
- **Output:** `str` — cleaned output, or original `raw` if stripping removes everything
- No new data structures. The return type of `run_lint_imports_check` remains `str`.

## Tests to add in `tests/test_checker_tools.py`

Add a new section `# --- _strip_lint_imports_header tests ---` with these test functions:

1. **`test_strip_lint_imports_header_removes_banner`** — Input has full logo + `Contracts` content -> output starts with `Contracts`, no box-drawing chars remain
2. **`test_strip_lint_imports_header_preserves_content_only`** — Input has no logo, just contract results -> output unchanged
3. **`test_strip_lint_imports_header_logo_only_falls_back`** — Input is only logo lines -> returns original raw input
4. **`test_strip_lint_imports_header_empty_string_falls_back`** — Empty string -> returns empty string (fallback)
5. **`test_strip_lint_imports_header_removes_dash_separators`** — Input has `---` separator lines around `Contracts` -> dashes removed, `Contracts` kept

Update `test_lint_imports_success_returns_raw_output`:
- Change the mocked `stdout` to include the ASCII banner + dashed separators + `Contracts: 2 kept, 0 broken`
- Assert the result does **not** contain box-drawing characters
- Assert the result **does** contain `Contracts: 2 kept, 0 broken`

## Commit

```
feat: strip lint-imports ASCII banner from tool output (#139)
```
