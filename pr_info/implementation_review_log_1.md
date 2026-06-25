# Implementation Review Log — Issue #193 (Run 1)

Branch: `193-macos-run-bandit-check-json-parse-failure-real-bug-pytest-verify-move-module-move-symbol-message-hardening`

Scope: bandit temp-file JSON capture + empty-file guard (Step 1); move_module/move_symbol AttributeError hint hardening (Step 2). Pytest item is verify-only (no code change).

---

## Round 1 — 2026-06-25

**Findings** (from `/implementation_review` engineer):
- Bandit temp-file capture (`runners.py`): matches issue-mandated approach (`-o <file>`, `mkdtemp`, read-back, `shutil.rmtree` in `finally`, error paths before file read). Correct.
- Empty/missing-file guard (`runners.py`): fires only on `return_code <= 1`, returns explicit error with `messages=[]`. Correct.
- move_module/move_symbol hint (`rope_tools.py`): hint appended via `isinstance(exc, AttributeError)` in existing broad handler, cleanup preserved, symmetric. Correct.
- Possible double-cleanup in `_move_module_impl`: `_cleanup_package` is idempotent — safe, no defect.
- Test quality: reworked to file seam; argv asserts include `-o <file>`; rope tests patch `create_move`. Solid.
- Guard test covered only the missing-file branch, not the empty-file (`getsize==0`) branch.
- Pytest item (#2): verify-only, out of scope.
- pylint/mypy pass; all issue-relevant tests pass. One unrelated pre-existing jedi cache flake in untouched `test_jedi_tools.py`.

**Decisions**:
- Accept: add an empty-file (`getsize==0`) guard test — the empty-file case is the realistic crash-after-open anomaly and the guard is the centerpiece of the fix; trivial/bounded.
- Skip: double-cleanup note (idempotent, no defect); pytest verify-only (out of scope); jedi flake (pre-existing, untouched file).
- No change: bandit capture, guard logic, move hint — all correct as implemented.

**Changes**: Added `test_zero_byte_output_file_is_error` to `tests/test_code_checker_bandit/test_runners.py`, exercising the empty-file branch (file exists, zero bytes → guard fires). No production code changed.

**Status**: pylint clean, mypy clean, pytest 540 passed / 1 skipped. Committed.

## Round 2 — 2026-06-25

**Findings**: None. Fresh review confirmed the new `test_zero_byte_output_file_is_error` exercises the empty-file (`getsize==0`) branch (distinct from the missing-file sibling), asserts the correct contract (`error is not None`, legible "output file" message, `messages==[]`), and matches existing style with no duplication. Production files (bandit capture/guard, move hints) still correct and complete.

**Decisions**: No changes needed.

**Changes**: None.

**Status**: Zero code changes — review loop complete. pylint clean, mypy clean, pytest 540 passed / 1 skipped.

## Round 3 (post-loop cleanup) — 2026-06-25

**Findings**: Supervisor `run_vulture_check` flagged a new 100%-confidence unused variable `cwd` in `tests/test_code_checker_bandit/test_runners.py:103` (`_write` helper inside `_writing_side_effect`), introduced by this branch. `run_lint_imports_check` PASSED (3 contracts kept).

**Decisions**: Accept the vulture fix (introduced by this branch → in scope). The `_cwd` underscore rename is invalid here because production calls `execute_command(cmd, cwd=project_dir)` with `cwd` as a keyword, so the side_effect param name is load-bearing. Used `del cwd` with an explanatory comment instead (vulture treats `del` as a use).

**Changes**: Added `del cwd  # ... intentionally unused` to the `_write` helper. Re-ran vulture (clean tree-wide), pylint, mypy, pytest — all pass.

**Status**: Committed (`6d9e346`).

---

## Final Status

- **Rounds run**: 2 review rounds (Round 1 found one accept-level gap → fixed; Round 2 found nothing) + 1 post-loop vulture cleanup.
- **Commits produced this review**:
  - `d934c1b` — test(bandit): cover zero-byte output file branch of empty-output guard
  - `6d9e346` — test(bandit): mark cwd param intentionally unused to satisfy vulture
  - (review log committed separately)
- **Implementation assessment**: All three issue #193 items correctly implemented per the mandated approach — bandit temp-file JSON capture with `-o <file>`, `mkdtemp`/`rmtree` lifecycle, error paths before file read, empty/missing-file anomaly guard (now branch-covered both ways); move_module/move_symbol AttributeError hint via `isinstance` in the existing broad handler with cleanup preserved. Pytest item is verify-only (macOS re-test, out of band).
- **Quality gates**: pylint clean · mypy clean · pytest 540 passed / 1 skipped (one unrelated pre-existing jedi cache flake in untouched `test_jedi_tools.py`) · vulture clean · lint-imports 3 contracts kept · black/isort clean.
- **No Critical findings. No architectural or import-contract violations.**
