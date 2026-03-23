# Implementation Review Log — Run 1

**Branch**: 108-add-python-refactoring-tools-rope-jedi
**Date**: 2026-03-23

## Round 1 — 2026-03-23

**Findings**:
- C1: RefactoringTools never registered in server.py — tools are dead code at runtime
- C2: tach.toml declares dependency on refactoring but import doesn't exist yet
- C3: Dry-run in move_symbol leaks files on disk if rope raises an exception
- S1: _ensure_parents walks to filesystem root instead of stopping at project root
- S2: _format_changes heuristic wrong after project.do() — all files show "Modified"
- S3: vulture_whitelist.py may need new tool entries
- S4: MCP tool name mismatch between plan docs and implementation
- S5: async def offset logic — confirmed correct
- S6: Architecture doc not updated
- S7: move_module dry-run error for missing destination

**Decisions**:
- C1: Accept (Critical) — bug, tools are dead code
- C2: Skip — resolved automatically by C1 fix
- C3: Accept — new code, cleanup not in finally block
- S1: Accept — new code, could create __init__.py above project dir
- S2: Accept — new code, misleading output in non-dry-run path
- S3: Skip — speculative ("may flag them")
- S4: Skip — pr_info/ is transient
- S5: Skip — confirmed correct
- S6: Skip — separate concern, follow-up issue
- S7: Skip — error message is clear; fixing adds complexity

**Changes**:
- server.py: Added import and registration of RefactoringTools (C1)
- rope_tools.py: Wrapped dry-run in try/finally with _cleanup_created_files helper (C3)
- rope_tools.py: Added project_dir param to _ensure_parents, updated 3 call sites (S1)
- rope_tools.py: Added pre_existing set param to _format_changes, added _collect_existing_paths helper, updated 3 operation functions (S2)

**Quality checks**: Pylint clean, Pytest 277 passed / 1 skipped, Mypy clean

**Status**: Committed as b755657

## Round 2 — 2026-03-23

**Findings**:
- S1: _cleanup_empty_dirs missing break on non-empty directory
- S2: _ensure_parents redundant existence check
- S3: _ensure_parents walk-up order — confirmed correct
- S4: vulture_whitelist missing new tool entries
- S5: Architecture doc not updated
- S6: Character vs byte offset edge case for non-ASCII

**Decisions**:
- S1: Accept — clarity fix, avoids unnecessary parent checks
- S2: Accept — dead guard, simplify
- S3: Skip — confirmed correct on inspection
- S4: Skip — speculative (same as round 1)
- S5: Skip — separate concern (same as round 1)
- S6: Skip — edge case for non-ASCII identifiers, speculative

**Changes**:
- rope_tools.py: Added else/break in _cleanup_empty_dirs for non-empty directories (S1)
- rope_tools.py: Removed redundant parent.exists() guard in _ensure_parents (S2)

**Quality checks**: Pylint clean, Pytest 277 passed / 1 skipped, Mypy clean

**Status**: Committed as 04fd785

## Round 3 — 2026-03-23

**Findings**:
- S1: _ensure_parents always breaks after one directory — only creates __init__.py for immediate parent
- S2: _cleanup_created_files reads file content unnecessarily

**Decisions**:
- S1: Accept — bug in new code, intermediate dirs miss __init__.py
- S2: Skip — defensively correct, cosmetic

**Changes**:
- rope_tools.py: Reordered _ensure_parents to check exists() before creating, so loop correctly walks up to existing package boundary

**Quality checks**: Pylint clean, Pytest 277 passed / 1 skipped, Mypy clean

**Status**: Committed as daff74a

## Round 4 — 2026-03-23

**Findings**: No critical issues, no new problems introduced by round 3.
**Decisions**: No changes needed.
**Status**: No changes — review complete.

## Final Status

- **Rounds**: 4 (3 with code changes, 1 verification)
- **Commits**: 3 (b755657, 04fd785, daff74a)
- **Issues fixed**: 7 (1 critical, 6 suggestions)
- **Branch**: CI passing, up to date with main, no rebase needed
- **Label**: status-07:code-review
- **Remaining**: Architecture doc update (deferred to follow-up)
