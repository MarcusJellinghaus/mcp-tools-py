# Step 1: Add `_strip_lint_imports_header()` helper with unit tests

> **Context:** See `pr_info/steps/summary.md` for full issue context (Issue #139).

## LLM Prompt

Implement the `_strip_lint_imports_header()` helper function and its unit tests in a TDD style. Write the tests first, then implement the function to make them pass. Run all code quality checks (pylint, pytest, mypy) and fix any issues before committing.

## WHERE

| File | Action |
|------|--------|
| `src/mcp_tools_py/checker_tools.py` | Add module-level function `_strip_lint_imports_header` (before the `CheckerTools` class) |
| `tests/test_checker_tools.py` | Add unit tests for the helper |

## WHAT

```python
# src/mcp_tools_py/checker_tools.py
import re

def _strip_lint_imports_header(raw: str) -> str:
    """Remove the import-linter ASCII art banner and dashed separators."""
```

## HOW

- Add `import re` to existing imports in `checker_tools.py`
- Place the function at module level, after imports and before the `CheckerTools` class
- No class changes in this step — integration happens in Step 2

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

## Tests to add in `tests/test_checker_tools.py`

Add a new section `# --- _strip_lint_imports_header tests ---` with these test functions:

1. **`test_strip_lint_imports_header_removes_banner`** — Input has full logo + `Contracts` content → output starts with `Contracts`, no box-drawing chars remain
2. **`test_strip_lint_imports_header_preserves_content_only`** — Input has no logo, just contract results → output unchanged
3. **`test_strip_lint_imports_header_logo_only_falls_back`** — Input is only logo lines → returns original raw input
4. **`test_strip_lint_imports_header_empty_string_falls_back`** — Empty string → returns empty string (fallback)
5. **`test_strip_lint_imports_header_removes_dash_separators`** — Input has `---` separator lines around `Contracts` → dashes removed, `Contracts` kept

## Commit

```
feat: add _strip_lint_imports_header helper (#139)
```
