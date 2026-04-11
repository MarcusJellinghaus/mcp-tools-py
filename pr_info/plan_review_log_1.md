# Plan Review Log — Issue #149 (Bandit Security Linter)

## Round 1 — 2026-04-11

**Findings**:
- (Important) Missing `code_checker_bandit` in `.importlinter` forbidden-imports contract
- (Important) `bandit>=1.7.0` too low — plan assumes pyproject.toml auto-discovery (requires 1.7.5+)
- (Important) Return code 2 handling copied from ruff, but bandit doesn't document code 2; changed to `> 1`
- (Important) Step 5 claims "no tests needed" but integration tests for binary detection and registration are missing
- (Important) Dependency should be applied during planning per planning principles
- (Minor) Misleading note about `errors` field defaulting to `[]` — it's a required field

**Decisions**:
- Accept #3: Add forbidden-imports entry in Step 6
- Accept #6: Bump version to `>=1.7.5` in Step 1 and summary
- Accept #9: Change `return_code == 2` to `return_code > 1` in Step 4
- Accept #11: Add integration tests to Step 5
- Accept #13: Add pre-requisite note to Step 1 about applying dependency during planning
- Accept #2: Remove misleading defaults text
- Skip 10 minor/informational findings (correct as-is or design choices)

**User decisions**: None needed — all findings were straightforward improvements.

**Changes**:
- `pr_info/steps/summary.md`: version bump, added test_integration.py to files table
- `pr_info/steps/step_1.md`: version bump, removed misleading defaults note, added pre-requisite section
- `pr_info/steps/step_4.md`: return code handling broadened, test renamed
- `pr_info/steps/step_5.md`: added integration test file and test descriptions
- `pr_info/steps/step_6.md`: added forbidden-imports entry instructions
- `pr_info/steps/Decisions.md`: created with all 6 decisions logged

**Status**: Committed (8624d50)

## Round 2 — 2026-04-11

**Findings**:
- (Important) Step 4 pseudocode omits `return_code` in BanditResult error-path construction
- (Important) Step 5 pseudocode missing explicit `binary = self._server._bandit_binary` access pattern
- (Minor) Step 2 algorithm doesn't explicitly show error dict → string formatting
- (Minor) CheckerTools class docstring not updated to include bandit (and ruff)
- (Minor) BanditResult helper methods not needed despite "mirrors" claim — acceptable as-is

**Decisions**:
- Accept #2: Fix BanditResult construction to always include return_code
- Accept #6: Add explicit binary access and availability check pattern
- Accept #4: Clarify error dict formatting in Step 2
- Accept #14: Add note to update CheckerTools docstring
- Skip #1: Already clear in plan

**User decisions**: None needed.

**Changes**:
- `pr_info/steps/step_4.md`: Fixed BanditResult error-path pseudocode with explicit return_code
- `pr_info/steps/step_5.md`: Added binary access pattern and docstring update note
- `pr_info/steps/step_2.md`: Clarified error dict → string formatting

**Status**: Pending commit
