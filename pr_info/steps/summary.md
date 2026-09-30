# Summary — Issue #236: strict ruff/pylint/bandit parsing, read-only `run_ruff_check`

## Problem

1. The ruff, pylint and bandit JSON parsers accept any dict and fill missing fields
   with defaults (`-1`, `0`, `""`). Ruff's `--statistics` JSON (per-rule summaries)
   therefore became fake violations at `:-1:-1`.
2. `run_ruff_check` can modify files: `--fix` / `--fix-only` in `extra_args`, or
   `fix = true` / `fix-only = true` in the project's ruff config. The same config
   breaks `run_ruff_fix`'s pre-check.

## Design changes

- **Strict parsing (main fix).** Each parser gets one private
  `_invalid_reason(item) -> str | None` next to it. An entry that is not a dict, or
  lacks a required field, turns the whole parse into an error naming the cause and
  the entry's keys. The hint "an argument in extra_args probably changed the
  output shape" is added by the pylint and bandit parsers, and for ruff by the
  checker runners only when `extra_args` were passed (the ruff parser is shared
  with the formatter, which has no `extra_args`). Ruff checks location first.
  Required = present and non-null; location fields must be `int`
  (`bool` rejected). All other fields keep their defaults and accept `null`.

  | Parser | Required | Integers |
  |---|---|---|
  | ruff | `code` (key present), `message`, `filename`, `location.row`, `location.column` | `row`, `column` |
  | pylint | `path`, `line`, `column`, `symbol`, `message-id` | `line`, `column` |
  | bandit | `test_id`, `filename`, `line_number` | `line_number` |

  Ruff `code: null` (older ruff syntax errors, used by the formatter) is normalised
  to `"invalid-syntax"` instead of being rejected. This intentionally deviates
  from the issue's "`code` required and non-null" rule; it keeps
  `tests/test_ruff_imports_runner.py::test_syntax_error_still_runs_fix` passing.
- **Bandit.** Missing or non-list `results` is an error. `cwe_id` stays `int`
  (`0` = no id); the report omits the CWE line when `cwe_id` is `0`.
- **Ruff command building.** `_build_ruff_command` appends, after `extra_args` and
  before the target paths, `--no-fix --no-fix-only` when `fix=False`, and
  `--no-fix-only` when `fix=True`. Last flag wins in ruff, so project config and
  caller flags cannot make a non-fix command write files.
- **Ruff flag pre-check.** One helper `_rejected_flag(extra_args, flags)` in
  `code_checker_ruff/runners.py`, exact-token match, called before ruff runs:
  `run_ruff_check_impl` rejects `--statistics`, `--fix`, `--fix-only`;
  `run_ruff_fix_impl` rejects `--statistics` only. Not a growing deny-list.

No new modules, no changed public signatures, no model changes.

## Files modified

```
src/mcp_tools_py/utils/ruff_parsing.py              (step 1)
src/mcp_tools_py/code_checker_ruff/runners.py       (step 2)
src/mcp_tools_py/checker_tools/ruff_check_tool.py   (step 2, docstring only)
src/mcp_tools_py/code_checker_pylint/parsers.py     (step 3)
src/mcp_tools_py/code_checker_bandit/parsers.py     (step 4)
src/mcp_tools_py/code_checker_bandit/reporting.py   (step 4)

tests/test_code_checker_ruff/test_parsers.py        (step 1)
tests/test_code_checker_ruff/test_runners.py        (step 2)
tests/test_code_checker_pylint/test_parsers.py      (step 3)
tests/test_code_checker_bandit/test_parsers.py      (step 4)
tests/test_code_checker_bandit/test_reporting.py    (step 4)
```

## Files created

```
tests/test_code_checker_ruff/test_integration.py    (step 2)
```

## Out of scope

- Mypy parser (no `extra_args`, skips non-JSON lines on purpose).
- `formatter/ruff_runner.py::run_ruff_imports` pre-check lacks `--no-fix-only`
  (separate follow-up issue).

## Steps

1. [step_1.md](./step_1.md) — strict ruff parser
2. [step_2.md](./step_2.md) — ruff command overrides and flag pre-check
3. [step_3.md](./step_3.md) — strict pylint parser
4. [step_4.md](./step_4.md) — strict bandit parser and CWE line
