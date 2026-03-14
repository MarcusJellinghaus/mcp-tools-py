# Step 4: Test file updates (rename, slim down, update signature tests)

> **Context**: Read `pr_info/steps/summary.md` for the full issue overview. This step depends on Steps 1-3 being complete. It fixes test breakage from Step 2 and aligns test coverage with the new interface.

---

## Part A: Rename test_integration_show_details.py -> test_integration_formatting.py

### WHERE
- **Rename**: `tests/test_code_checker_pytest/test_integration_show_details.py` -> `tests/test_code_checker_pytest/test_integration_formatting.py`

### WHAT
1. **Rename** the file
2. **Rename** the test class: `TestIntegrationShowDetails` -> `TestIntegrationFormatting`
3. **Remove** tests that test the `show_details=False` toggle path (these paths are no longer exercised since `show_details` is always `True`):
   - `test_standard_ci_run` — tests `show_details=False` producing compact output
   - `test_smart_hints_for_small_runs` — tests "Try show_details=True" hint
   - `test_real_world_usage_patterns` — tests False->True toggle workflow
4. **Keep** all tests that validate detailed output formatting works correctly (called with `show_details=True`):
   - `test_focused_debugging_session`
   - `test_large_test_suite_with_failures`
   - `test_specific_test_with_prints`
   - `test_marker_filtering_with_details`
   - `test_verbose_pytest_with_show_details`
   - `test_no_tests_found_with_show_details`
   - `test_all_tests_pass_with_show_details`
   - `test_collection_errors_with_show_details`
   - `test_output_length_management`
   - `test_performance_validation`
   - `test_clean_temporary_file_handling`

### DATA
No changes to kept test logic — they all already call with `show_details=True`.

---

## Part B: Update test_server_params.py

### WHERE
- **Modify**: `tests/test_server_params.py`

### WHAT — Remove tests that assert removed parameters

**Remove these tests** (they assert `verbosity`/`show_details` in the signature):
- `test_run_pytest_check_show_details_default_value` — asserts `show_details` in signature
- `test_server_method_signature_includes_show_details` — asserts `show_details` in signature
- `test_parameter_type_validation` — asserts `verbosity` annotation and default

**Remove `show_details`/`verbosity` assertions from these tests** (keep the tests, update assertions):
- `test_run_pytest_check_with_show_details_true` — remove `show_details=True` from call, keep rest of test logic
- `test_run_pytest_check_with_show_details_false` — remove `verbosity=1` from call, keep rest
- `test_show_details_with_focused_test_run` — simplify: both calls should now show detailed output (no more False->True toggle)
- `test_show_details_with_many_failures` — simplify similarly
- `test_show_details_output_length_limits` — remove `show_details=True` from call (always True now)
- `test_run_pytest_check_parameters` — remove `verbosity=3` from call, update mock assertion (no `verbosity` in call args)
- `test_run_pytest_check_backward_compatibility` — keep as-is (tests calling without optional params)
- `test_mcp_tool_decorator_compatibility` — keep as-is
- `test_enhanced_reporting_integration_preparation` — remove `show_details=True` from call

### WHAT — Update mock assertions for check_code_with_pytest calls

When tests mock `check_code_with_pytest` and assert call args, the `verbosity` value now comes from `sanitize_extra_args` (default 2), not from the function parameter:

```python
# Before:
mock_check.assert_called_once_with(
    ...
    verbosity=3,       # was passed as parameter
    extra_args=["--no-header"],
    ...
)

# After:
mock_check.assert_called_once_with(
    ...
    verbosity=2,       # default from sanitize_extra_args
    extra_args=["--no-header", "-s"],  # -s always appended
    ...
)
```

### WHAT — Add new tests

**Add test for simplified signature:**
```python
def test_run_pytest_check_simplified_signature():
    # Assert signature has: markers, extra_args, env_vars
    # Assert signature does NOT have: verbosity, show_details
```

**Add test for defensive error handling:**
```python
def test_run_pytest_check_never_raises():
    # Mock check_code_with_pytest to raise RuntimeError
    # Assert run_pytest_check returns a string (not raises)
    # Assert string contains "Unexpected error"
```

**Add test for deduplication notes in output:**
```python
def test_run_pytest_check_prepends_dedup_notes():
    # Call with extra_args=["-m", "slow"] AND markers=["unit"]
    # Assert result starts with "Note: -m flag in extra_args was ignored..."
```

### HOW
The existing test infrastructure (mock_server fixture, _get_tool helper) remains unchanged.
Tests that call `run_pytest_check` need to also mock or patch `sanitize_extra_args` where appropriate, or let it run naturally since it's a pure function.

---

## Verification
After this step:
- `pytest tests/test_server_params.py` passes
- `pytest tests/test_code_checker_pytest/test_integration_formatting.py` passes
- `pytest tests/test_code_checker_pytest/test_extra_args.py` passes (from Step 1)
- `pytest tests/` — full test suite passes
- `mypy src/ tests/` passes
- `pylint src/` passes
