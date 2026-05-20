# Summary: Fix `-s` Forced Append and Truncated INTERNALERROR on Exit 3

## Issue Reference
GitHub Issue **#192** — `run_pytest_check forces -s, causing xdist worker crashes; truncated error hides root cause`.

## Problem Statement

Two independent bugs in `run_pytest_check`:

1. **Forced `-s` flag.** `checker_tools/pytest_tool.py:93-94` unconditionally appends `-s` to every pytest invocation, and `code_checker_pytest/utils.py:56-58` silently strips any user-supplied `-s`. Combined with `-n auto` (xdist), `-s` bypasses pytest's capture machinery that `execnet` IPC relies on, crashing worker processes with `OSError: [Errno 9] Bad file descriptor`.
2. **Truncated INTERNALERROR on exit code 3.** `code_checker_pytest/runners.py:356-363` runs the combined output through `_build_error_detail`, which uses a 500-character `truncate_stderr` cap from `mcp-coder-utils`. The pytest `INTERNALERROR>` block — the only thing that identifies the crashing test — is cut off, leaving the user with misleading unrelated stderr.

## Architectural / Design Changes

These are surgical bug fixes — no new modules, no new public APIs, no parameter additions.

- **Inversion of `-s` defaulting.** The flag moves from "always auto-added" to "user opt-in via `extra_args=["-s"]`". The implementation already matched what the docstring promised; this aligns the code with the documented behavior.
- **Conflict resolution pattern extended.** `sanitize_extra_args` already handles `-m` vs. `markers` parameter conflict by stripping with a note. The same pattern now handles the `-s` vs. xdist conflict — strip `-s` when `["-n", VALUE]` is present with VALUE ≠ `"0"`, emit a note so the caller self-corrects.
- **Error-path information preservation.** The exit-code-3 branch now scans for pytest's `INTERNALERROR>` lines and prepends them verbatim and untruncated. `_build_error_detail` and the 500-char cap stay intact for the rest of the message; the fix bypasses the cap only for the diagnostic slice that needs to survive.
- **Form scope (deliberate limitation).** The xdist strip handles only the two-arg `["-n", VALUE]` form, consistent with how the existing `-m` handling is scoped. `--numprocesses` long form passes through unchanged and is documented in the limitations comment.

No changes to data models, public function signatures, module boundaries, or the dependency graph.

## Files to Modify

| File | Change |
|------|--------|
| `src/mcp_tools_py/checker_tools/pytest_tool.py` | Remove unconditional `+ ["-s"]` append at lines 93-94. |
| `src/mcp_tools_py/code_checker_pytest/utils.py` | Remove unconditional `-s` strip at lines 56-58. Add conditional xdist-aware strip after the main loop. Update limitations docstring. |
| `src/mcp_tools_py/code_checker_pytest/runners.py` | In the exit-code-3 branch (lines 356-363) extract `INTERNALERROR>` lines from combined output and prepend them untruncated to the raised `RuntimeError` message. |
| `tests/test_code_checker_pytest/test_extra_args.py` | Update `test_s_flag_removed_silently` and `test_combined_deduplication` to reflect lone-`-s` passthrough. Add new cases for `-s` + `-n auto` (strip+note), `-s` + `-n 0` (preserve), and `--numprocesses` long form (passthrough). |
| `tests/test_server_params.py` | Update expected `extra_args` at lines 73-82 from `["--no-header", "-s"]` to `["--no-header"]`; fix the inline `-s is always appended` comment. |
| `tests/test_code_checker/test_runners.py` | Add a regression test (sibling of the `internal_error_3` parametrized case at lines 394-403) using a realistic multi-line `INTERNALERROR>` block long enough to exceed the 500-char truncation cap. |

**Files created:** none.
**Files deleted:** none.
**Modules / folders touched:** `src/mcp_tools_py/checker_tools/`, `src/mcp_tools_py/code_checker_pytest/`, `tests/test_code_checker_pytest/`, `tests/test_code_checker/`, `tests/`.

## Implementation Steps

| Step | Title | Commit Scope |
|------|-------|--------------|
| 1 | Drop forced `-s`, add conditional xdist strip | `pytest_tool.py` + `utils.py` + affected tests |
| 2 | Preserve `INTERNALERROR>` on exit code 3 | `runners.py` + regression test |

Each step is self-contained: tests are updated/added first (TDD red), implementation follows (green), and all three quality gates (`pylint`, `pytest`, `mypy`) pass before commit.

## Out of Scope

- `--numprocesses` long-form handling (documented limitation).
- Combined short flags like `-xvs` (existing limitation, unchanged).
- Raising the global `MAX_STDERR_IN_ERROR` cap (owned by `mcp-coder-utils`; issue explicitly forbids).
- Broadening INTERNALERROR preservation to other exit-code branches (issue explicitly scopes to exit 3).
