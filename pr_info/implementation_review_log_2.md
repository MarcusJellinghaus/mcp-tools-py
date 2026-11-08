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

## Round 2 — 2026-11-08
**Findings**: none new. Verified: conftest markers under `testpaths` still load with `--rootdir`; multi-marker exclusion joins with `and`; 600 s check timeout yields to `[tool.mcp-tools-py]` settings; `_build_context` guards catch every `PythonEnvironment.resolve` failure; the autouse `VIRTUAL_ENV` fixture only clears inherited state.
**Decisions**: n/a
**Changes**: none
**Status**: no changes needed

## Final Status
- Rounds: 2 (1 with code changes: `--rootdir` on the marker read, `f9bfb8c`).
- Vulture: one false positive (autouse fixture `_clear_virtual_env`) → added to `vulture_whitelist.py`; now clean.
- lint-imports: 4 contracts kept, 0 broken.
- CI passed on `f9bfb8c`; branch up to date with `main`; no open issues remain.
