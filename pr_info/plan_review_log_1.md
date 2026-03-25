# Plan Review Log — Issue #111

**Issue**: run_pytest_check extra_args path filter does not restrict test collection
**Branch**: 111-run-pytest-check-extra-args-path-filter-does-not-restrict-test-collection
**Date**: 2026-03-25

## Round 1 — 2026-03-25

**Findings**:
- Critical: Steps 1 and 2 should be merged — Step 1 alone has no tangible result (has_path_args is dead code until Step 2 wires it). Violates "every step must have tangible results" principle.
- Critical: Missing integration-level test for the actual bug scenario — need a test that validates the full command construction (path in extra_args → default test folder omitted from command).
- Accept: Root cause analysis and fix approach are correct.
- Accept: Path detection algorithm handles edge cases well (flags, absolute paths, node IDs, non-existent paths).
- Accept: Backward compatibility preserved via defaults on all new parameters/fields.
- Accept: Test plan for sanitize_extra_args path detection is comprehensive.
- Accept: skip_default_test_folder explicit boolean parameter is appropriately scoped.
- Skip: -k expression false-positive concern is theoretically present but practically safe due to os.path.exists guard.

**Decisions**:
- Merge Steps 1 and 2 into single step — accept (straightforward, aligns with planning principles)
- Add integration-level test — accept (straightforward, tests the actual bug scenario)

**User decisions**: None — both items were straightforward improvements.

**Changes**:
- Merged step_1.md and step_2.md into a single combined step_1.md
- Deleted step_2.md
- Added integration test (test_path_args_skip_default_folder_integration) to test plan
- Updated summary.md to reflect single implementation step

**Status**: Committed

## Final Status

- **Rounds**: 1
- **Changes**: Steps merged, integration test added
- **Plan status**: Ready for approval
