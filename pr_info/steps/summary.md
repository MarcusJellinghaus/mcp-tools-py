# Summary — #294 run_pytest_check: show the effective pytest config (addopts, markers)

## Goal

`run_pytest_check` tells the LLM which pytest defaults applied (`addopts` from the
project and `PYTEST_ADDOPTS`) and, when a `-m` run fails because of a marker name,
which name is wrong and which markers the project registers. The docstring and the
README document how to clear the defaults and how to pick markers.

The issue text (#294) is the requirement. Its decisions 1–19 and its Acceptance list
are binding; this plan only fixes *how*.

## Architectural / design changes

1. **One reader of the pytest config, in `code_checker_pytest/pytest_config.py`.**
   - `read_pytest_config(project_dir) -> PytestConfig | None` reads `pyproject.toml`
     (`[tool.pytest.ini_options]` or `[tool.pytest]`) and detects pytest config files
     that win over it (`pytest.toml`, `.pytest.toml`, `pytest.ini`, `.pytest.ini`;
     `tox.ini [pytest]` / `setup.cfg [tool:pytest]` only when `pyproject.toml` has no
     pytest section). It never raises: any read failure, or both pytest tables
     non-empty, gives `None`.
   - `effective_config(project_dir, markers, cleaned_args, env_vars) -> EffectiveConfig`
     combines ini `addopts`, `PYTEST_ADDOPTS` (from `os.environ` overlaid with
     `env_vars`) and the call, in pytest's order. A single generic option scanner
     (all spellings: `-X v`, `-Xv`, `-X=v`, `--long v`, `--long=v`) runs in two passes:
     pass 1 over `PYTEST_ADDOPTS` + call for `-o addopts=…` and `-c`/`--config-file`;
     pass 2 over the applied token sources for the last `-m`, `-k`, `-n`, and
     strictness (`--strict-markers`, `--strict`, `-o strict_markers=`, `-o strict=`).
   - `addopts_notes(effective) -> list[str]` renders the `addopts` lines (decision 6)
     or the "not read" note (decision 8).
   - Replaces `get_pytest_addopts` (`utils/project_config.py`, deleted) and
     `_effective_option` / `_option_value` (`coverage.py`, deleted).

2. **Coverage selection uses the same helper.** `selection_line` and
   `selection_identity` take the `EffectiveConfig` instead of an `addopts` string.
   This fixes the list join (`shlex.join`), `-m=X`, an explicit empty `-m`,
   `[tool.pytest]`, `PYTEST_ADDOPTS`, `-o addopts=` and `-c`, and appends the
   "not read" note. The toolkit's `full` depth calls it with `env_vars=None`.

3. **Exit code transport in `runners.py`.** `run_tests` sets two attributes on the
   exception it re-raises (same mechanism as `_COMMAND_ATTR`): the pytest exit code,
   and `marker_error` — pytest's `ERROR:` line from the **full** stderr, set only
   when it is `Unknown marker(s) in '-m' expression` or `Wrong expression passed to
   '-m'`. `check_code_with_pytest` returns them as keys `exit_code` and
   `marker_error`. `RunVerdict.exit_code` stays 0 on the error path; the 500-char cut
   of `_build_error_detail` is unchanged. (Decision 18's "marker-error flag" is
   `marker_error is not None`; its kind is the message text.)

4. **Marker hint in `code_checker_pytest/marker_hint.py`.**
   - `scan_expression(expr)` — one pass over pytest's `-m` grammar: names, whether
     each is under an odd number of `not`s, and whether the expression is valid. A
     paren-parity stack replaces a recursive-descent parser; a two-state
     operand/operator check gives validity. No `_pytest` import.
     This is an equivalent implementation of decision 17's recursive-descent parse,
     not a change to it: pytest's `-m` grammar has no precedence that affects
     negation parity, so a stack of `not` parities per paren level plus the
     operand/operator state and a strict `name(key=value, …)` check accept exactly
     the expressions the grammar accepts, without recursion.
   - `marker_notes(effective, exit_code, marker_error) -> list[str]` — pytest's
     `ERROR:` line, the hint, the `--strict-markers` suggestion and the `-n 0` rerun
     tip (decisions 11–13, 15, 17, 19).

5. **Wiring only in `run_pytest_check`** (`checker_tools/pytest_tool.py`). It builds
   the `EffectiveConfig` once, uses it for the coverage selection, and prepends
   `addopts_notes` (when defaults could explain the result, decision 5) and
   `marker_notes` before the existing top notes. Nothing goes into
   `verdict.problems`; `check_code_with_pytest`'s callers in the toolkit get no new
   lines.

6. **Docs**: `run_pytest_check` docstring, README parameter rows, architecture doc.

## Files

Created:
- `src/mcp_tools_py/code_checker_pytest/pytest_config.py`
- `src/mcp_tools_py/code_checker_pytest/marker_hint.py`
- `tests/test_code_checker_pytest/test_pytest_config.py`
- `tests/test_code_checker_pytest/test_effective_config.py`
- `tests/test_code_checker_pytest/test_marker_hint.py`
- `tests/test_code_checker_pytest/test_config_notes_reply.py`
- `tests/test_code_checker_pytest/test_integration_marker_hint.py`

Modified:
- `src/mcp_tools_py/code_checker_pytest/coverage.py`
- `src/mcp_tools_py/code_checker_pytest/runners.py`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `src/mcp_tools_py/toolkit.py`
- `src/mcp_tools_py/utils/project_config.py` (remove `get_pytest_addopts`)
- `tests/test_code_checker_pytest/conftest.py` (autouse `PYTEST*` scrub; not
  `tests/conftest.py`, which would break `tests/test_startup_time.py`)
- `tests/test_project_config.py` (remove `TestGetPytestAddopts`)
- `tests/test_code_checker_pytest/test_coverage.py`
- `tests/test_code_checker_pytest/test_coverage_selection_identity.py`
- `tests/test_code_checker_pytest/test_runners.py`
- `tests/test_toolkit_test.py` / `tests/test_toolkit.py` (only if they reference
  `get_pytest_addopts` or the old `selection_*` signatures)
- `README.md`
- `docs/architecture/architecture.md`

## Steps

1. `read_pytest_config` + `PYTEST*` test-env scrub.
2. `effective_config` + `addopts_notes`.
3. Coverage selection on `EffectiveConfig`; delete `get_pytest_addopts`.
4. `runners.py`: `exit_code` / `marker_error` transport.
5. `marker_hint.py`: `scan_expression`, `marker_notes`.
6. Wire notes into `run_pytest_check`; reply-level and real-pytest tests.
7. Docstring, README, architecture doc.

## Checks per step

`run_format_code`, then `run_pylint_check`, `run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`,
`run_mypy_check`, `run_vulture_check`, `run_lint_imports_check`. Steps that add
`integration` tests also run those test files. Each step is one commit.

## Known limits (from the issue, not addressed)

conftest/plugin markers not listed; config files outside the project root;
`[tool.pytest]` on pytest 8; `testpaths` from `[tool.pytest]`; pytest 8 strictness
resolved with pytest 9 rules. `PYTEST_CURRENT_TEST` is re-set by pytest each test
phase, so the scrub fixture cannot keep it out; it doesn't affect selection.
