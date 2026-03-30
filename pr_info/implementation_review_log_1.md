# Implementation Review Log — Issue #130

**Branch**: 130-sync-update-subprocess-runner-py-from-mcp-coder-env-inheritance-fix
**Date**: 2026-03-30
**Reviewer**: Supervisor agent

---

## Round 1 — 2026-03-30

**Findings**:
- C1. `_run_subprocess` does not use `prepare_env()` — the core bug fix is not wired in
- C2. `execute_subprocess` missing heartbeat integration — `_run_heartbeat` is dead code
- C3. `_run_subprocess` still uses `preexec_fn` (removed in upstream, threading concern)
- C4. Missing `encoding="utf-8"` and `errors="replace"` on Popen/subprocess.run calls
- C5. `utils/__init__.py` not updated with new exports / has extra exports vs upstream
- S1. `sys.platform == "win32"` vs upstream `os.name == "nt"` (cosmetic)
- S2. `prepare_env()` removes `CLAUDECODE` key not present in upstream
- S3. `_run_heartbeat` docstring more verbose than upstream (cosmetic)
- S4. Brittle `inspect`-based test for type annotation (speculative)
- S5. Broad `except Exception` in `execute_subprocess` — upstream narrows to specific types

**Decisions**:
- C1: **Accept (Critical)** — Core purpose of issue #130, must wire in
- C2: **Accept (Critical)** — Dead code without this, functional gap
- C3: **Accept** — Thread-safety, bounded fix, matches upstream
- C4: **Accept** — Prevents crashes on invalid UTF-8, matches upstream
- C5: **Accept** — Align re-exports with upstream pattern
- S1: **Accept** — Part of overall upstream alignment effort
- S2: **Accept** — Unexplained divergence from upstream, remove
- S3: **Accept** — Part of overall upstream alignment effort
- S4: **Skip** — Test works, mypy covers it, speculative breakage
- S5: **Accept** — Real concern, swallows unexpected errors

**Changes**:
- Replaced inline env logic in `_run_subprocess` with `prepare_env()` call
- Added heartbeat params to `execute_subprocess` with thread setup/teardown
- Removed `_safe_preexec_fn`, replaced with `start_new_session` only
- Added `encoding="utf-8"` and `errors="replace"` to all Popen/subprocess.run calls
- Replaced `structlog`/`structured_logger` with plain `logger` + f-strings
- Narrowed exception handlers to match upstream
- Removed `CLAUDECODE` removal from `prepare_env`
- Changed `get_utf8_env` to use `os.name == "nt"` and `env.update()` style
- Shortened `_run_heartbeat` docstring
- Aligned `launch_process` with upstream (cwd_str conversion, docstring)
- Narrowed `__init__.py` re-exports to match upstream
- Updated tests for new API signatures

**Status**: Committed (3313884)

## Round 2 — 2026-03-30

**Findings**:
- 2.1 Missing provenance comment in module docstring (cosmetic)
- 2.2 Redundant exception subclasses in handler (matches upstream)
- 3.1 Unused test imports for re-exported exceptions (implicit re-export test)
- 3.2 Missing inline comments on type:ignore directives (cosmetic)
- 3.3 Fragile inspect-based test (already skipped in round 1)
- 3.4 Trimmed __init__.py API — verified no consumers break

**Decisions**: All **Skip** — cosmetic, matches upstream exactly, or already addressed

**Changes**: None

**Status**: No changes needed

## Final Status

- **Rounds**: 2
- **Commits**: 1 (3313884)
- **Open issues**: None — all critical and accept items resolved in round 1
- **Upstream alignment**: subprocess_runner.py now mirrors p_coder reference
