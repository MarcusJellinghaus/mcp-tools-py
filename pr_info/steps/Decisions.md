# Decisions

## 1. Update reporting module signatures alongside runners

The call chain is checker_tools → reporting → runners. Changing runner `target_directories` params from `Optional[list[str]]` to `list[str]` without updating the intermediate reporting functions (`get_pylint_prompt`, `get_mypy_prompt`) would cause mypy type errors, since reporting would still accept `None` and pass it through.

**Decision:** Update `code_checker_pylint/reporting.py` and `code_checker_mypy/reporting.py` signatures in Step 3 to match.

## 2. Refactor formatter_tools.py to use shared resolve_target_directories()

`formatter_tools.py` already has the same inline directory resolution pattern being replaced in checker tools. Using the shared helper completes the DRY consolidation (Boy Scout Rule).

**Decision:** Include `formatter_tools.py` refactoring in Step 3.

## 3. Replace vulture whitelist test instead of removing it

The whitelist computation still happens in `checker_tools.py` (it is passed to the runner). Removing the test would lose coverage for that handoff.

**Decision:** Replace `test_vulture_whitelist_auto_included` with `test_vulture_passes_whitelist_to_runner` that patches `run_vulture_check` and verifies the correct `whitelist_path` argument is passed.
