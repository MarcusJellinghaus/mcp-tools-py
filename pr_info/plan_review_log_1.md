# Plan Review Log — Issue #121 (Add lint-imports as MCP tool)

## Round 1 — 2026-03-26

**Findings**:
- (Critical) `test_all_tools_available` expects `"lint-imports": False` — misleading for a test named "all tools available"
- (Critical) Windows binary path missing `.exe` extension — inconsistent with existing `python.exe` pattern, unreliable on Windows
- (Skip) `execute_command` import reminder — already noted in the plan
- (Skip) DRY violation with binary path in 2 places — only 2 occurrences, helper abstraction is premature per KISS/YAGNI
- (Accept) `TestToolHandlerShortCircuit` tests need `"lint-imports"` key added to manually-set availability dicts
- (Accept) `mock_server` fixture in `test_checker_tools.py` needs `"lint-imports": True` and `venv_path`
- (Skip) `tach.toml` no-change note — informational, correct
- (Skip) "No output" fallback string — minor UX detail, fine as-is

**Decisions**:
- Accept finding 1: mock lint-imports binary as available so test lives up to its name
- Accept finding 2: use `lint-imports.exe` on Windows, consistent with `python.exe` pattern
- Skip finding 3: already noted in the plan
- Skip finding 4: only 2 occurrences, KISS over DRY for this scope
- Accept finding 5: explicitly note short-circuit test fixture updates in step 2
- Accept finding 6: explicitly note mock_server fixture updates in step 2
- Skip findings 7-8: no action needed

**User decisions**: None — all accepted findings were straightforward improvements

**Changes**:
- `pr_info/steps/step_1.md`: Fixed `test_all_tools_available` to expect `"lint-imports": True` with mocked binary; fixed Windows path to `lint-imports.exe`
- `pr_info/steps/step_2.md`: Fixed Windows path to `lint-imports.exe`; added sections for updating `TestToolHandlerShortCircuit` and `mock_server` fixtures

**Status**: committing
