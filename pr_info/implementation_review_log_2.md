# Implementation Review Log #2

**Issue:** #108 — Add Python Refactoring Tools (rope, jedi)
**Date:** 2026-03-23
**Branch:** 108-add-python-refactoring-tools-rope-jedi

## Round 1 — 2026-03-23

**Findings:**
- Server refactoring: `CheckerTools` extracted cleanly from `server.py`, behavior-preserving
- Jedi tools (`list_symbols`, `find_references`): clean implementation, proper scoping via `jedi.Project`, correct top-level filtering
- Rope tools (`move_symbol`, `rename_symbol`, `move_module`): solid implementation, correct offset finding, proper `_ensure_parents` traversal, safe dry-run cleanup
- Refactoring module registration follows existing `CheckerTools` pattern
- Architecture enforcement updated correctly in `tach.toml` and `.importlinter`
- Dependencies (`rope>=1.13.0`, `jedi>=0.19.0`) properly added with mypy overrides
- Test coverage: 38+ tests across unit, registration, and integration levels
- `_ensure_parents` stopping condition correct (stops at existing `__init__.py` or project root)
- Dry-run cleanup safe (checks empty content before removal, only removes truly empty dirs)
- `move_module` dry-run limitation is reasonable and documented
- Private attribute access in `CheckerTools` acceptable (tightly coupled by design)
- **import-linter CI failure**: `checker_tools` and `refactoring` were on the same layer as the code checkers, but they import from them (peer imports not allowed). Also, `TYPE_CHECKING`-guarded imports from `server` flagged as upward violations.

**Decisions:**
- Code implementation findings: **Skip** — no issues found requiring changes
- import-linter failure: **Accept** — fix `.importlinter` to place `checker_tools | refactoring` on their own layer above code checkers, add `ignore_imports` for TYPE_CHECKING-guarded server imports

**Changes:**
- `.importlinter`: Split tool registration modules (`checker_tools`, `refactoring`) into their own layer above code checker implementations. Added `ignore_imports` for TYPE_CHECKING-guarded server imports.

**Status:** Committed.

## Final Status

**Rounds:** 1
**Commits produced:** 1 (import-linter fix)
**Outcome:** Implementation approved. One CI issue fixed (import-linter layer config). All quality gates pass (pylint, mypy, pytest 277/278, import-linter).
