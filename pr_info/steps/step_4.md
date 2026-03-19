# Step 4: Integration test file rename and cleanup

> **Context**: Read `pr_info/steps/summary.md` for the full issue overview. This step depends on Steps 1-3 being complete. It handles the integration test file rename and removal of obsolete `show_details=False` toggle tests.

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

## Verification
After this step:
- `pytest tests/test_code_checker_pytest/test_integration_formatting.py` passes
- `pytest tests/test_code_checker_pytest/test_extra_args.py` passes (from Step 1)
- `pytest tests/test_server_params.py` passes (from Step 2)
- `pytest tests/` — full test suite passes
- `mypy src/ tests/` passes
- `pylint src/` passes
