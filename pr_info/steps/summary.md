# Summary — Issue #256: move_symbol dry-run side effects and hidden changes; run_pytest_check collect count

Rule for this issue: `move_symbol` only does what rope does. We fix bugs and add read-only reporting. There's no custom code-rewriting logic on top of rope.

## Goals

1. **A dry run writes nothing.** That includes a dry run that times out. Cleanup moves from the rope child process to the parent, so a hard kill can't skip it.
2. **A real run that fails or times out reports what happened.** The parent re-parses the source and destination files and lists moved vs not-moved symbols. If nothing moved, it also removes the files and dirs this call created.
3. **`timeout_seconds` per call** on the `move_symbol` MCP tool.
4. **A dry run shows the real diff.** Each symbol gets one unified diff from rope's `ChangeSet.get_description()`.
5. **A string-reference report** in the dry run and the real run. It lists string literals that refer to a moved name, such as `@patch("pkg.mod.name")`, marked "not rewritten".
6. **The collect count is correct with `-m`.** The header reads `Collected N tests (M deselected)`, where `N = collected - deselected`.

## Architectural / design changes

- **Cleanup ownership moves to the parent.** Before it launches the rope subprocess, `rope_tools.move_symbol()` takes a snapshot of the paths that don't exist yet: the destination file, plus each missing parent dir and its `__init__.py` up to `project_dir`. After the child exits or is killed, it removes the snapshotted paths that now exist. Files go first, and a dir goes only if it's empty. A short retry loop handles `PermissionError`, since on Windows a just-killed child may still hold handles.
  - Dry run: cleanup always runs.
  - Real run that fails: cleanup runs only if the re-parse shows no requested symbol moved.
  - Real run that succeeds: no cleanup.
- **Child-side cleanup is gone for `move_symbol`.** `_cleanup_created_files` is deleted. `_cleanup_empty_dirs` stays because `_cleanup_package`, used by `move_module`, still calls it. `move_module` and `rename_symbol` don't change.
- **Real-run failures follow one flat rule** in `move_symbol()`:
  1. If the result starts with `move_symbol completed successfully.`, return it unchanged.
  2. Otherwise, re-parse and split the names into moved and not moved.
  3. If none moved, clean up. For validation errors this does nothing, because they create nothing.
  4. If the result starts with `Error` (a timeout, an exit or run error, or `Error moving symbol:`), append the moved/not-moved listing and the note to check `git diff`. Validation errors (`Duplicate…`, `Symbol '…' not found`, `Name collision…`) don't start with `Error`, so they come back unchanged.
- **The new reporting is read-only and runs inside the child.**
  - Diffs: in a dry run, `changes.get_description()` for each symbol, taken before any `project.do`. There's no diffing code of our own.
  - String references: `_string_ref_lines()` walks `project.get_python_files()`, which respects the gitignore-based ignores, and scans each file with `ast` for `ast.Constant` strings. A string `s` matches when `s == old` or `s.startswith(old + ".")`, where `old = "<source dotted module>.<name>"`. The source module's dotted path comes from its package root.
- **Code placement.** All new helpers go in `rope_tools.py`, which is already on the large-files allowlist. The new rope tests go in `test_rope_tools.py` and must keep it under 750 lines.

## Files modified

| File | Change |
|------|--------|
| `src/mcp_tools_py/code_checker_pytest/reporting.py` | `get_test_summary` header uses the selected count and adds `(M deselected)` |
| `src/mcp_tools_py/refactoring/__init__.py` | `move_symbol` tool: `timeout_seconds` parameter and docstring notes |
| `src/mcp_tools_py/refactoring/rope_tools.py` | Parent-side snapshot and cleanup, re-parse of moved symbols, dry-run diffs, string-reference scan; `_cleanup_created_files` removed |
| `tests/test_code_checker/test_reporting.py` | Collect-count tests |
| `tests/test_refactoring/test_refactoring_tools.py` | `timeout_seconds` plumbing test |
| `tests/test_refactoring/test_rope_tools.py` | Cleanup, failure, diff and string-reference tests |

No folders, modules or files are created apart from these plan files.

## Steps

1. `step_1.md`: collect count with deselected tests.
2. `step_2.md`: per-call `timeout_seconds` on the `move_symbol` tool.
3. `step_3.md`: parent-side snapshot cleanup for dry runs.
4. `step_4.md`: real-run failure reporting and cleanup; remove `_cleanup_created_files`.
5. `step_5.md`: dry-run diffs.
6. `step_6.md`: string-reference report.

Each step is one commit: tests, implementation, then pylint, pytest, mypy and the formatter all passing.
