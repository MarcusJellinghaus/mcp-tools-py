# Step 6 — Wire the notes into `run_pytest_check`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_6.md`), and
> issue #294 (decision 5, Constraints "Placement", "The toolkit's unattended contract
> must keep working", "Tests", and the whole Acceptance list). Steps 1–5 are done.
> Implement step 6 only: tests first, then code, run the checks listed in the
> summary plus the new integration test file, then commit (one commit).

## WHERE

- Modified: `src/mcp_tools_py/checker_tools/pytest_tool.py`
- Modified: `src/mcp_tools_py/code_checker_pytest/pytest_config.py` (one helper)
- New: `tests/test_code_checker_pytest/test_config_notes_reply.py` (mocked)
- New: `tests/test_code_checker_pytest/test_integration_marker_hint.py` (real pytest,
  `@pytest.mark.integration`)

## WHAT

```python
# pytest_config.py
def call_replaced_addopts_m(effective: EffectiveConfig) -> bool:
    """True when the call's -m (markers or extra_args) replaced an -m from addopts or PYTEST_ADDOPTS."""

# pytest_tool.py (module level, private)
def _defaults_may_explain(
    test_results: dict[str, Any], collect_only: bool, effective: EffectiveConfig
) -> bool:
    """Decision 5: deselected, no tests found, failed/error, suspicious, or a replaced -m."""
```

## HOW

- `effective` is already built after `sanitize_extra_args` (step 3).
- After `result = checker_tools._format_pytest_result_with_details(...)`:

```python
top = addopts_notes(effective) if _defaults_may_explain(test_results, sanitized.collect_only, effective) else []
top += marker_notes(effective, test_results.get("exit_code"), test_results.get("marker_error"))
notes = [*top, *([test_paths_note] if test_paths_note else []), *sanitized.notes]
```

  The existing `if notes:` prepend stays; the new lines are not subtracted from
  `max_lines` / `max_chars` (as the existing notes). Nothing is added to
  `verdict.problems`.
- `check_code_with_pytest` and the toolkit are untouched.

## ALGORITHM — `_defaults_may_explain`

```
status = test_results["verdict"].status; summary = test_results.get("summary") or {}
if status in (FAILED, ERROR): return True          # exit 3/4/5, missing report included
deselected = summary.get("deselected") or 0
if deselected or (summary.get("collected") or 0) - deselected == 0: return True
if status is SUSPICIOUS and not collect_only: return True
return call_replaced_addopts_m(effective)
```

`call_replaced_addopts_m`: `effective.m` source is `markers` or `extra_args`, and an
`-m` event occurs in `ini_tokens` (when `ini_source != "PYTEST_ADDOPTS"` too) or
`env_tokens` (reuse `_option_events`).

## DATA

Reply order: `addopts` lines / not-read note → pytest's `ERROR:` line → marker hint →
`--strict-markers` suggestion → rerun tip → test-paths note → sanitize notes → blank
line → existing reply.

## Tests (write first)

`test_config_notes_reply.py` — through `run_pytest_check`, using the fixture pattern
of `tests/test_code_checker_pytest/test_output_budget.py` (`run_pytest_check`
fixture). Patch `mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest` with
`make_pytest_results(...)` (`tests/_pytest_results.py`) plus the `exit_code` /
`marker_error` keys, except where noted.

- clean full pass with `addopts = "-n auto"` → no `addopts` line.
- deselected > 0 → `addopts (pyproject.toml): … — to run without: extra_args=["-o", "addopts="]`.
- failed run, ERROR run, SUSPICIOUS run → line present.
- `--collect-only` SUSPICIOUS without deselection → no line; with deselection → line.
- passing run with `markers=["fast"]` and addopts `-m 'not slow'` → replaced line
  naming `markers`; with `extra_args=["-m", ""]` → replaced, naming `extra_args`.
- `env_vars={"PYTEST_ADDOPTS": "-x"}` on a failure → `PYTEST_ADDOPTS: -x — to run
  without: env_vars={"PYTEST_ADDOPTS": ""}`; `env_vars={"PYTEST_ADDOPTS": ""}` → none.
- `pytest.ini` in the root on a failure → `pytest config is in pytest.ini, not read`.
- `markers=["unit"]`, exit 5, config without strict → `No Tests Found` reply plus
  hint and suggestion, notes before `Problems:`.
- `addopts = "-m unit"`, exit 5 → `addopts` line and hint.
- toolkit unattended contract: `markers=UNATTENDED_EXCLUDED_MARKERS`,
  `extra_args=["-o", "strict_markers=false"]`, project `addopts =
  "--strict-markers"`, exit 5 → no marker hint.
- exit 4 via real `run_tests`: patch
  `mcp_tools_py.code_checker_pytest.runners.execute_command` with
  `make_command_result(4, stderr=<600 chars of warnings> + "\nERROR: Unknown marker(s) in '-m' expression: unit. Use 'pytest --markers' to see available markers.")`
  and `extra_args=["-m", "unit"]` → reply contains that `ERROR:` line and the hint.

`test_integration_marker_hint.py` — real pytest via `check_code_with_pytest` +
`marker_notes` / `addopts_notes`, or through `run_pytest_check`, each in its own
`tmp_path` project (own `pyproject.toml`, so this repo's `-n auto --strict-markers`
does not apply). `pytest.importorskip("xdist")` where `-n` is used; skip below
pytest 9 (`pytest.version_tuple < (9,)`) for exit-4 / exit-3 marker cases and
`[tool.pytest]`.

- `-m unit`, no strict, no `unit` marker → exit 5, hint + suggestion.
- `--strict-markers` project, `-m unit`, no `-n` → pytest's `Unknown marker(s)` line
  + hint, no suggestion.
- same with `-n 2` → exit 3, hint + `RERUN_TIP`.
- `-m "a and"` (syntax error) with `-n 2` → `RERUN_TIP`; without `-n` → exit 4
  `Wrong expression passed to '-m'` line, no tip; with `-n 0` → no tip.
- `[tool.pytest]` project with `addopts = ["-m", "unit"]` → same `addopts` line and
  hint as the `ini_options` variant.
