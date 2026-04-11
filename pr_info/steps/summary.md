# Issue #151 — Extract plain `run_format_code()` + port line-length pre-check

## Goal

Make the formatter orchestration logic callable as a plain Python function
(enabling `mcp_coder` to call it directly), and add a line-length conflict
pre-check. The MCP tool surface remains unchanged — same args, same string
output.

## Architecture / Design Changes

### Before

```
formatter_tools.py (MCP closure contains ALL logic)
├── step validation
├── directory resolution
├── tool availability check
├── runner loop + fail-fast
└── string formatting

black_runner.py  → returns tuple[str, bool]
isort_runner.py  → returns tuple[str, bool]
```

### After

```
formatter/models.py          ← NEW: FormatterResult dataclass
formatter/runner.py          ← NEW: plain run_format_code() function
formatter/formatter_tools.py ← MODIFIED: thin MCP wrapper delegates to runner.py
formatter/black_runner.py    ← MODIFIED: returns FormatterResult (with files_changed)
formatter/isort_runner.py    ← MODIFIED: returns FormatterResult (with files_changed)
utils/project_config.py      ← MODIFIED: add check_line_length_conflicts()
```

**Key separation**: `runner.py` owns orchestration logic (step validation,
runner loop, fail-fast). `formatter_tools.py` owns MCP concerns (tool
availability, dir resolution, result→string formatting, line-length warnings).

### Data flow change

```
Before:  MCP closure → runner(…) → tuple[str, bool] → string assembly → return str
After:   MCP wrapper → run_format_code(…) → dict[str, FormatterResult] → string assembly → return str
```

### Architectural constraints preserved

- `utils/project_config.py` has no formatter imports (import-linter clean)
- `formatter` layer imports `utils` but not vice versa
- No new layer dependencies in `tach.toml` or `.importlinter`

## Files Created

| File | Purpose |
|------|---------|
| `src/mcp_tools_py/formatter/models.py` | `FormatterResult` dataclass |
| `src/mcp_tools_py/formatter/runner.py` | Plain `run_format_code()` function |
| `tests/test_formatter_runner.py` | Tests for `run_format_code()` |

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/formatter/black_runner.py` | Return `FormatterResult`, parse `files_changed` |
| `src/mcp_tools_py/formatter/isort_runner.py` | Return `FormatterResult`, parse `files_changed` |
| `src/mcp_tools_py/formatter/formatter_tools.py` | Thin wrapper, delegates to `runner.py` |
| `src/mcp_tools_py/formatter/__init__.py` | Export new public symbols |
| `src/mcp_tools_py/utils/project_config.py` | Add `check_line_length_conflicts()` |
| `tests/test_black_runner.py` | Update for `FormatterResult`, add `files_changed` tests |
| `tests/test_isort_runner.py` | Update for `FormatterResult`, add `files_changed` tests |
| `tests/test_formatter_tools.py` | Update for new delegation pattern |
| `tests/test_project_config.py` | Add `check_line_length_conflicts` tests |

## Implementation Steps

| Step | Scope | Commit message |
|------|-------|----------------|
| 1 | `FormatterResult` model + update both runners to return it | `refactor(formatter): add FormatterResult model, update runners` |
| 2 | Extract `run_format_code()` into `runner.py`, update `formatter_tools.py` to delegate | `refactor(formatter): extract run_format_code into runner.py` |
| 3 | Add `check_line_length_conflicts` in `project_config.py`, wire into MCP wrapper | `feat(formatter): add line-length conflict pre-check` |
