# Issue #37: Improve pytest extra_args handling

## Goal
Simplify the `run_pytest_check` MCP tool interface, add smart `extra_args` deduplication, and improve error messages so LLMs can self-correct.

## Architectural / Design Changes

### Interface Simplification
- **Remove** `verbosity` and `show_details` parameters from the `run_pytest_check` MCP tool signature
- **Hard-code** `-vv` as default verbosity; allow override via `extra_args` (`-v`, `-vvv`)
- **Always** show detailed failure output (`show_details=True` internally)
- **Always** add `-s` flag for print statement capture
- Internal functions (`check_code_with_pytest`, `run_tests`) keep their `verbosity` parameter unchanged

### New Sanitization Layer
- New `SanitizedArgs` dataclass in `models.py` (consistent with existing `ErrorContext`, `PytestReport` pattern)
- New `sanitize_extra_args()` function in `utils.py` that deduplicates and cleans `extra_args` before passing to internal functions
- Deduplication notes are both logged (structlog) and prepended to the tool result string

### Error Propagation
- `runners.py`: Include raw stderr/stdout in the error string returned by `check_code_with_pytest()`
- `server.py`: Defensive try/except wrapping the **entire** `run_pytest_check` body, guaranteeing a string return (never raises)

### Data Flow (changed path marked with *)
```
MCP Client
  -> run_pytest_check(markers, extra_args, env_vars)     # * simplified signature
     -> sanitize_extra_args(extra_args, markers)          # * NEW
     -> check_code_with_pytest(..., verbosity=extracted)   # unchanged
        -> run_tests(...)                                  # unchanged
     -> _format_pytest_result_with_details(..., True)      # * always True
     -> prepend notes to result string                     # * NEW
  <- result string (never raises)                          # * defensive
```

## Files Modified

| File | Change |
|------|--------|
| `src/mcp_code_checker/code_checker_pytest/models.py` | Add `SanitizedArgs` dataclass |
| `src/mcp_code_checker/code_checker_pytest/utils.py` | Add `sanitize_extra_args()` function |
| `src/mcp_code_checker/code_checker_pytest/__init__.py` | Export `SanitizedArgs` |
| `src/mcp_code_checker/server.py` | Simplify `run_pytest_check` signature, integrate sanitization, defensive try/except |
| `src/mcp_code_checker/code_checker_pytest/runners.py` | Include raw stderr/stdout in error messages |

## Files Created

| File | Purpose |
|------|---------|
| `tests/test_code_checker_pytest/test_extra_args.py` | Unit tests for `sanitize_extra_args()` |

## Files Renamed / Updated

| File | Change |
|------|--------|
| `tests/test_code_checker_pytest/test_integration_show_details.py` -> `test_integration_formatting.py` | Rename; remove `show_details=False` toggle/hint tests |
| `tests/test_server_params.py` | Remove `verbosity`/`show_details` signature tests; add deduplication + defensive error tests |

## Implementation Steps

1. **Step 1** - `SanitizedArgs` dataclass + `sanitize_extra_args()` function with unit tests
2. **Step 2** - `server.py` interface simplification + defensive error handling
3. **Step 3** - `runners.py` error propagation improvement
4. **Step 4** - Test file updates (rename, slim down, update signature tests)

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| Keep `verbosity` in internal functions | Smallest internal change, `run_tests()` stays reusable |
| Keep `_format_pytest_result_with_details()`, `should_show_details()`, helpers | Less churn, easy to re-enable `show_details` toggle later |
| `SanitizedArgs` dataclass in `models.py` | Consistent with `ErrorContext`, `PytestReport` pattern |
| `sanitize_extra_args()` in `utils.py` | Consistent — `utils.py` already has pytest-specific helpers |
| Defensive try/except wraps entire function body | Guarantees string return, LLM always gets actionable output |
| Let FastMCP handle unknown params | No dead code for backwards compatibility |
