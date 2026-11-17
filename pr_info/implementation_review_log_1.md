# Implementation Review Log — Run 1

Branch: `chore/align-quality-checks-with-mcp-coder`
Issue: #107 (chore list; epic section "Align quality checks with mcp_coder", mcp_coder#1163)
Reference: mcp_coder's `pyproject.toml`, `.github/workflows/ci.yml`, tools and workflows — follow them as closely as possible.

## Round 1 — 2026-11-17
**Findings**:
1. `probe.py` cast uses runtime `X | Y` (UP007 ignore for target_scripts dropped in 651d05c) — breaks `get_library_source` on 3.9 targets
2. `CONTRIBUTING.md` references nonexistent `tools\format_all.bat` (2 places)
3. `test_startup_time.py` skip message calls the startup-budget step a "job"
4. `docs/upgrade-notes.md` lacks a note on the unwrapped `search_library_files` output
5. `ci.yml` forbidden-folders job drops mcp_coder's unused `check_empty_folder`
6. `ci.yml` mypy entry installs `.[dev]` instead of `.[typecheck]`
7. `tools/checks2clipboard.bat` still runs `pylint -E`

**Decisions**:
1. Accept — real regression; mcp_coder has no target-run scripts, so no conflict with following it
2. Accept — broken doc reference
3. Accept — trivial wording
4. Accept — client-visible change, the file exists for exactly this
5. Skip — unused here, same behaviour
6. Skip — matches mcp-workspace template; mypy is a runtime dep here
7. Accept only to align with mcp_coder — mcp_coder has no such file, so no change

**Changes**: `probe.py` back to `typing.Union` + `UP007` per-file ignore restored in `pyproject.toml`; `CONTRIBUTING.md` uses `ruff check --select I --fix` + `ruff format`; skip message wording; upgrade note added.
**Status**: committed

## Round 2 — 2026-11-17
**Findings**:
1. `tools/lint_imports.bat`, `tools/tach_check.bat` not synced with mcp_coder — always exit 0, no tool guard, no `%*`
2. `pyproject.toml` pytest `addopts = "-n auto"` differs from mcp_coder (`--strict-markers --tb=short -p no:tach`)
3. `upstream-mypy-check.yml` keeps `enable-cache: false` on `setup-uv`

**Decisions**:
1. Accept — swallowed exit codes; mcp_coder's versions fix it
2. Skip — pytest config not in #107's checklist; `--strict-markers` changes behaviour
3. Skip — cosmetic, no effect

**Changes**: both `.bat` files copied verbatim from mcp_coder.
**Status**: committed

## Round 3 — 2026-11-17
**Findings**:
1. `ci.yml` lacks mcp_coder's new advisory `check-sensitive-files` job (mcp_coder#1435, merged 2026-11-17)
2. `tools/mypy.bat` differs from mcp_coder (no explicit `--strict` flag set; same effect via pyproject)
3. `tools/ruff_check.{bat,sh}` header comment hand-reworded vs mcp_coder
4. `tools/check_version.bat` still lists black/isort
5. `CONTRIBUTING.md` names nonexistent `git_status.bat` / `test_cli_installation.bat`, old pylint flag
6. `CONTRIBUTING.md` `run_format_code` sentence omits that `tools/` isn't formatted by default
7. `target_scripts` per-file ignore covers UP007 only, not UP045

**Decisions**:
1. Skip — outside epic #1163 and newer than the sync; flag to the user as a new #107 chore item
2. Accept — verbatim copy
3. Accept — verbatim copy
4. Accept — stale after the ruff-format switch; minimal edit
5. Skip — pre-existing, out of scope
6. Skip — same gap in mcp_coder
7. Skip — speculative (no `Optional` in probe.py)

**Changes**: `mypy.bat` and `ruff_check.{bat,sh}` copied verbatim from mcp_coder (`ruff_check.sh` stays 100755); `check_version.bat` lists `ruff --version` instead of black/isort.
**Status**: committed

## Round 4 — 2026-11-17
**Findings**:
1. `tools/check_version.bat` doesn't list `deptry --version` although deptry is now a CI job (mcp-workspace's copy lists it)

**Decisions**:
1. Accept — one line, matches the mcp-workspace template

**Changes**: `deptry --version` added after `lint-imports --version`, copied from mcp-workspace.
**Status**: committed

## Round 5 — 2026-11-17
**Findings**:
1. `.large-files-allowlist` has 3 stale entries for files now under the limit

**Decisions**:
1. Skip — untouched by this branch, check passes, unrelated cleanup

**Changes**: none
**Status**: no changes needed

## Final Status
- Rounds: 5 (4 with changes, round 5 clean)
- Commits: 6f0b546, 04c52f7, 82c5e84, e43d7f5
- vulture: clean; lint-imports: 4 kept, 0 broken
- CI passed on e43d7f5; no rebase needed; no PR yet
- Open, outside this branch: mcp_coder's new advisory `check-sensitive-files` CI job (mcp_coder#1435) → candidate chore item for #107
