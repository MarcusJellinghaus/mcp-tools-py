# Implementation Summary — Issue #171

## Goal

Make `run_lint_imports_check` surface contract failures reliably to the LLM,
even when the MCP transport truncates the output.

## Problem (one paragraph)

The current handler ignores `result.return_code` and pipes raw stdout/stderr
through `_strip_lint_imports_header`, which over-aggressively drops any line
containing box-drawing characters. When a long combined response is truncated,
the BROKEN summary line and the failing-contract details are hidden — the LLM
sees only a benign "No matches for ignored import" warning and treats it as a
clean run. A real BROKEN `Layered Architecture` contract was missed during code
review because of this.

## Architectural / Design Changes

1. **New thin checker package**
   `src/mcp_tools_py/code_checker_lint_imports/` with one file (`runners.py`)
   plus `__init__.py` — same shape as `code_checker_tach/` and
   `code_checker_vulture/`. No `models.py` / `parsers.py` / `reporting.py`
   split: lint-imports has too little structure to justify it. (Bandit's
   four-file split exists for grouping/sorting JSON records, which does not
   apply here.) The issue text suggests mirroring `code_checker_bandit/`'s
   four-file split, but single-file matches `code_checker_tach/` /
   `code_checker_vulture/` better here: lint-imports has no parsed-message
   records to group/sort and no JSON shape — it shares the same
   plain-text-parsing shape as tach/vulture, not the structured-record
   shape that justifies bandit's split.

2. **Three-state pipeline inside one orchestrator**
   `run_lint_imports_check_impl(binary, project_dir, extra_args) -> str`
   does: strip `-v`/`--verbose` → run subprocess → parse summary +
   broken-contract names + warnings → classify
   (`PASSED` / `BROKEN` / `ERROR`) → format with state header on top → cap.

3. **State header is the load-bearing piece**
   The state header is emitted at the top of the output (above which only an
   optional info line about stripped flags can appear). Truncation cannot hide
   it. This is the smallest change that fixes the original symptom.

4. **No per-contract detail-block extraction**
   The full raw stdout is included beneath the structured header (within the
   line cap). Broken contract names are listed in the header so the LLM can
   re-run with `--contract <name>`. Sidesteps the regex-bounds problem the
   issue flags as needing fixture confirmation.

5. **`--verbose` / `-v` are stripped**
   from caller-supplied `extra_args`. An info line above the state header
   notes the removal. Reason: both add only progress chatter and duplicate
   contract-status lines, breaking the parser without adding new information.

6. **Line cap with explicit truncation marker**
   `MAX_OUTPUT_LINES = 300` redeclared locally (not imported from pytest's
   `OutputBuilder`). Marker:
   `[output truncated — run with --contract <name> for individual results]`.
   Cap also applies in the ERROR fallback.

7. **`_strip_lint_imports_header` is retired**
   together with `_BOX_DRAWING_OR_ARROWS` and `_ONLY_DASHES` regexes in
   `checker_tools.py`. Its 5 helper tests in `tests/test_checker_tools.py`
   are removed; the 2 handler tests are replaced by structured equivalents
   under `tests/test_code_checker_lint_imports/`.

8. **Layered architecture self-update**
   The new package is registered in both `.importlinter` (third layer of
   `[importlinter:contract:layers]` and `forbidden_modules` of the
   `forbidden-imports` contract) and `tach.toml` (own module entry under
   `tool_implementation`, plus `checker_tools.depends_on`).

## State Classification (authoritative table)

| `return_code` | summary line parsed? | `broken_count` | State    |
|---------------|----------------------|----------------|----------|
| 0             | yes                  | 0              | PASSED   |
| ≠ 0           | yes                  | > 0            | BROKEN   |
| any           | other combination    | —              | ERROR    |

Three states is the issue's explicit decision (table row #5).

## Output Layout

```
[Info: stripped --verbose / -v from extra_args]      # only when applicable
=== <STATE_HEADER> ===
Contracts: N kept, M broken                          # when summary parsed
Broken contracts:                                    # when state == BROKEN
  - <name>
  - <name>
Warnings:                                            # when warnings present
  - No matches for ignored import X -> Y.

<raw stdout / stderr body, capped>
[output truncated — run with --contract <name> for individual results]
```

State header strings:

- `PASSED`
- `BROKEN: M of N contracts failed`
- `ERROR: lint-imports output could not be parsed`

## Files Created or Modified

### Created

- `src/mcp_tools_py/code_checker_lint_imports/__init__.py`
- `src/mcp_tools_py/code_checker_lint_imports/runners.py`
- `tests/test_code_checker_lint_imports/__init__.py`
- `tests/test_code_checker_lint_imports/test_runners.py`

### Modified

- `src/mcp_tools_py/checker_tools.py`
  - `_register_lint_imports`: delegate to new impl, update docstring.
  - Remove `_strip_lint_imports_header`, `_BOX_DRAWING_OR_ARROWS`, `_ONLY_DASHES`.
  - Remove unused `re` import (verify before deleting — used elsewhere).
- `tests/test_checker_tools.py`
  - Remove the 5 `_strip_lint_imports_header` tests (lines ~227-272).
  - Remove the 2 obsolete handler tests (lines ~166-224).
  - Remove the `_strip_lint_imports_header` import.
- `.importlinter`
  - Add `mcp_tools_py.code_checker_lint_imports` to layered third layer.
  - Add it to the `forbidden-imports` contract's `forbidden_modules`.
- `tach.toml`
  - Add a `[[modules]]` entry for `mcp_tools_py.code_checker_lint_imports`
    (layer = `tool_implementation`, depends_on utils + log_utils).
  - Add it to `mcp_tools_py.checker_tools.depends_on`.

## Step Plan

Each step is one commit: tests + implementation + all three quality checks
green.

1. **Step 1** — Build the new checker package (TDD).
2. **Step 2** — Wire `checker_tools.py` to the new impl; remove old helper
   and its tests; update architecture configs (`.importlinter`, `tach.toml`).

The split is deliberate: step 1 introduces the new package in isolation
(green tests, no behavior change to the live tool yet); step 2 swaps the
production call site, deletes the dead helper, and self-registers the new
package architecturally — all of which must land together to keep
`.importlinter` and `tach` green.

## Out of Scope

- Per-contract detail-block parsing (decision: include raw stdout instead).
- Reusing `code_checker_pytest.OutputBuilder` (decision: redeclare local cap).
- Library-API integration with import-linter (decision: subprocess only).
