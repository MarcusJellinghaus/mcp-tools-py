# Implementation review log 2 — issue #276

Supervisor-driven review after rebase onto `main` (0552518).

## Round 1 — 2026-11-08
**Findings**:
- `toolkit.py` `_registered_markers` + real run each get the full pytest timeout, so `test@quick` can take up to 2× the budget (minor).
- Marker read omits `--rootdir project_dir` (which the real run passes) and doesn't bump `PYTEST_SUBPROCESS_DEPTH` (minor).
- `pr_info/steps/summary.md` still says "no `--rootdir` and no PATH tweaks" (doc drift).
- Rebased `_with_note` / `test_paths_note` integration verified correct; no note exists before the marker-read early return.

**Decisions**:
- Double timeout: skip — reusing `resolve_timeout("pytest")` was a planned decision; the edge case is speculative.
- `--rootdir`: accept — one line, keeps the marker read consistent with the real run (same reasoning as the `venv_bin` fix).
- `PYTEST_SUBPROCESS_DEPTH`: skip — the marker read runs no tests, so the recursion guard doesn't apply.
- summary.md drift: skip — pr_info/ is deleted before merge.

**Changes**: `_registered_markers` passes `--rootdir <project_dir>`; new test `test_marker_read_passes_project_dir_as_rootdir` in `tests/test_toolkit_markers.py`.
**Status**: committed

