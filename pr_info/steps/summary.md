# Issue #193 — Implementation Summary

Three unrelated problems surfaced on macOS during a first run of the
`mcp-tools-py` MCP tools. Only **one is a real bug** (bandit); the other two are
a verification step and an error-message hardening.

| # | Item | Severity | Code change? |
|---|------|----------|--------------|
| 1 | `run_bandit_check` JSON parse failure (Rich progress bar on stdout) | Real bug | Yes — Step 1 |
| 2 | `run_pytest_check` "Internal pytest error" misclassification | Verify-only | No (see below) |
| 3 | `move_module` / `move_symbol` cryptic `NoneType.is_folder` error | Message hardening | Yes — Step 2 |

Steps 1 and 2 are independent → **two commits**.

---

## Item 1 — bandit temp-file capture (Step 1)

**Root cause.** `parse_bandit_json_output` is fed `result.stdout`. Newer bandit
(≥1.8) prints a Rich `Working… ━━━ 100%` progress bar to **stdout**, mixed with
the JSON, breaking `json.loads`. bandit is unpinned upward, so the two machines
run different versions.

**Fix (issue-mandated).** Have bandit write JSON to a **temp file via `-o <file>`**
and read it back — immune to anything bandit prints to stdout. This mirrors the
existing pytest `--json-report-file` pattern in
`code_checker_pytest/runners.py` (`mkdtemp` → temp file → `shutil.rmtree` in a
`finally`).

**Empty/missing-file guard.** A legitimate run always writes a complete JSON
object (even "no issues" → `"results": []`; unparseable sources still exit 0 and
record an `errors` entry). So an empty/missing file is **never** normal — it is a
genuine anomaly (crash before write, bad path, disk full). When the run looks
successful (`return_code <= 1`) but the file is missing/empty, return an explicit
error instead of silently reporting "no issues".

## Item 2 — pytest (verify-only, **no code change, not a numbered step**)

Likely already fixed by commit #207 (removed the unconditional `-s`; preserves
`INTERNALERROR>` lines on exit 3). The acceptance criterion is a **macOS-only
re-test** of the failing scenario against current `main`; it cannot be verified
from Windows/CI and produces no commit. Tracked as an out-of-band PR acceptance
gate, not an implementation step.

## Item 3 — move_module / move_symbol message hardening (Step 2)

The `NoneType.is_folder` `AttributeError` escapes rope's internals
(`MoveModule.get_changes`) when rope cannot analyze the source module. Fixing
rope is **out of scope**. The existing broad `except Exception` already preserves
the original exception text; the only new work is **appending an actionable
hint** whenever the caught exception is an `AttributeError`.

---

## Architectural / Design Changes

- **No new modules, classes, layers, or public signatures.** All changes are
  internal to two existing checker/refactoring modules; the MCP tool surface
  (`run_bandit_check`, `move_module`, `move_symbol`) is unchanged.
- **Bandit adopts the established file-seam pattern.** `code_checker_bandit`
  moves from parsing `stdout` to parsing a temp JSON file, making it consistent
  with `code_checker_pytest` (the only design-level shift). `_build_bandit_command`
  gains one `output_path` parameter; `run_bandit_check_impl` gains a
  `try/finally` temp-dir lifecycle and an anomaly guard. `BanditResult.raw_output`
  now carries file contents instead of stdout (it is informational only — not
  consumed downstream by `bandit_tool.py`).
- **KISS for item 3 — single handler, no duplication.** Rather than adding a
  second `except AttributeError` branch that duplicates each function's dry-run
  cleanup, the existing broad `except Exception` is kept and the hint is appended
  via `isinstance(exc, AttributeError)`. Cleanup stays in one place and cannot
  drift out of sync. The trigger is the exception **type** (`isinstance`), not a
  brittle match on the `NoneType ... is_folder` string — exactly as required.
- **No bandit version pin/cap.** The temp-file capture makes the version
  irrelevant.

---

## Folders / Modules / Files Created or Modified

**Modified — production**
- `src/mcp_tools_py/code_checker_bandit/runners.py` — `_build_bandit_command`
  (add `output_path` arg + `-o <file>`); `run_bandit_check_impl` (temp-dir
  lifecycle, read file, empty/missing-file guard, `finally` cleanup).
- `src/mcp_tools_py/refactoring/rope_tools.py` — `_move_module_impl` and
  `_move_symbol_impl` (append AttributeError hint in the existing broad handler).

**Modified — tests**
- `tests/test_code_checker_bandit/test_runners.py` — reworked to the file seam
  (`-o <file>` in argv asserts; `execute_command` mock `side_effect` writes the
  report file; new empty/missing-file guard test).
- `tests/test_refactoring/test_rope_tools.py` — add two tests asserting the
  AttributeError hint (one per `_impl`), original text preserved, no leaked dir.

**Created**
- `pr_info/steps/summary.md`, `pr_info/steps/step_1.md`, `pr_info/steps/step_2.md`
  (this plan).

**No files deleted. No new source modules or packages.**

---

## Per-step Quality Gate

After each step, all three MCP checks must pass (CLAUDE.md):
`run_pylint_check`, `run_pytest_check` (with
`-n auto -m "not git_integration and not claude_cli_integration and not claude_api_integration and not formatter_integration and not github_integration and not langchain_integration"`),
`run_mypy_check`. Run `./tools/format_all.sh` before committing.
