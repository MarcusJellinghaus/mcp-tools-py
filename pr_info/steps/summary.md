# Issue #139: Strip ASCII art header from lint-imports output

## Problem

The `import-linter` CLI emits a Unicode ASCII-art logo and dashed separators that render as garbled text in MCP clients and waste tokens.

## Solution

Add a module-level `_strip_lint_imports_header()` helper in `checker_tools.py` that removes the banner lines, then call it on the combined output before returning.

## Design Changes

**No architectural changes.** This is a single pure-function addition + one call-site edit:

- A new **module-level function** `_strip_lint_imports_header(raw: str) -> str` in `checker_tools.py` (not a method on the class — it has no dependencies on instance state).
- The existing `run_lint_imports_check` inner function applies the helper to `output` before returning.

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/checker_tools.py` | Add `_strip_lint_imports_header()`, call it in `run_lint_imports_check` |
| `tests/test_checker_tools.py` | Add unit tests for the helper; update existing integration test to verify stripping |

## Algorithm (`_strip_lint_imports_header`)

```
for each line in raw output:
    skip if line contains Box Drawing chars (U+2500–U+257F) or arrows (▶◀▲▼)
    skip if line consists only of dash characters
    otherwise keep the line
strip leading/trailing blank lines from kept lines
if nothing remains, return the original raw input
```

## Implementation Steps

- **Step 1**: Add `_strip_lint_imports_header()` with unit tests
- **Step 2**: Integrate the helper into `run_lint_imports_check` and update integration test
