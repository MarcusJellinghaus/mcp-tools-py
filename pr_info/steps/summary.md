# Summary: #49 run_pytest_check drops or misreports extra_args

## Goal

1. A positional `tests` or `tests/` is an ordinary path. An option's value is never treated as a path and is passed through unchanged. The default folder is never taken as an option's value.
2. `--collect-only` reports the selected count and the test IDs, and isn't reported as `Not verified`.
3. The formatter's failure text starts with its counts and adds `N of M selected tests did not run` when N > 0.

## Architectural / design changes

No new modules, no new `RunStatus`, no new dependencies.

- **Argument classification (`code_checker_pytest/utils.py`).** A hard-coded table maps each value-taking pytest option to how many values it can take. A small scanner uses it to split positionals from options. `sanitize_extra_args` runs path detection on those positionals only, instead of on every non-dash token.
- **One rule for option values.** An option takes up to N following tokens that don't start with `-`. N is 1 for most options, including the optional-value ones (`--cov`, `--debug`, `--cache-show`), 2 for `--metadata`, and unbounded for `--json-report-omit`. This removes separate handling for argparse's optional and one-or-more forms. It also removes special cases for dash-prefixed values: `--maxfail -1` and `-k "-a b"` are skipped as dash tokens and never read as paths.
- **Unknown options keep today's behaviour.** They take no value, so a following token is still a positional.
- **`--`.** Everything after it is positional in the scanner. The switch-extraction loop in `sanitize_extra_args` does not look at `--`. pytest's real behaviour depends on position and Python version (on 3.11, `-- test_x.py -k test_a` still applied `-k`), so tests pin the scanner, not pytest.
- **Command order (`runners.py`).** The default folder goes before `extra_args`, so a trailing option can't take it as a value.
- **Failure reply (`checker_tools/__init__.py`).** The order becomes counts, did-not-run line, `Collection problems` block, details. Counts sit outside the 300-line cap, so truncation can't hide them.
- **Collect-only.** `SanitizedArgs.collect_only` is detected from the arguments and passed to the formatter, which branches inside the existing `SUSPICIOUS` case. Collection errors still classify as `ERROR`. `toolkit.py` never passes `extra_args`, so it keeps the `Not verified` text, with the corrected count.

## Accepted limits

- Passing `tests` in a project with no `tests/` folder becomes a usage error instead of silently running the default folder. The coverage selection for `["tests"]` also stops matching `[]`.
- `<path> <path> --keep-duplicates` reports `4 of 8 selected tests did not run`, because the JSON report merges tests by nodeid.
- Odd calls such as `-k "-x k" <path>` or `--metadata -a b` can give a wrong path decision. The arguments still reach pytest unchanged.
- The table can go stale. An option missing from it keeps today's behaviour, so there is deliberately no drift test.
- The `Pytest run reported no outcomes` server-log warning still fires for collect-only. The reply is correct; only the log line is unchanged.

## Files

Created:

- `tests/test_code_checker_pytest/test_integration_extra_args.py`

Modified:

| File | Step |
|---|---|
| `src/mcp_tools_py/code_checker_pytest/utils.py` | 1, 3 |
| `src/mcp_tools_py/code_checker_pytest/runners.py` | 1, 3 |
| `src/mcp_tools_py/code_checker_pytest/reporting.py` | 2, 3 |
| `src/mcp_tools_py/checker_tools/__init__.py` | 2, 3 |
| `src/mcp_tools_py/code_checker_pytest/models.py` | 3 |
| `src/mcp_tools_py/code_checker_pytest/verdict.py` | 3 |
| `src/mcp_tools_py/checker_tools/pytest_tool.py` | 3 |
| `src/mcp_tools_py/toolkit.py` | 3 |
| `README.md` | 2, 3 |
| `tests/test_code_checker_pytest/test_extra_args.py` | 1, 3 |
| `tests/test_code_checker/test_runners.py` | 1 |
| `tests/test_code_checker_pytest/test_reporting.py` | 2 |
| `tests/test_checker_tools_formatting.py` | 2, 3 |
| `tests/test_code_checker_pytest/test_verdict.py` | 3 |

Tests that pass a `MagicMock` report into the FAILED path may also need a real `Summary` in step 2 (see that step).

## Steps

1. [step_1.md](./step_1.md): arguments (option table, scanner, positional `tests`, folder first)
2. [step_2.md](./step_2.md): failure reply (counts first, did-not-run line)
3. [step_3.md](./step_3.md): collect-only (reply with IDs, corrected suspicious count)

Step 1 must land before #58, which depends on it.

## Out of scope

`--durations` output (#44), `--collect-only` through `addopts`, `--setup-plan`, `--fixtures`, and coverage arguments being added after a `--`.
