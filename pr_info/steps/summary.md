# Summary — #238 Coverage through `run_pytest_check`

## Goal

`run_pytest_check(coverage=True)` runs the suite under pytest-cov and appends a
compact **coverage digest** to the normal pytest reply: total, worst modules
ranked by absolute missing statements, per-function missing line ranges, a
separate zero-coverage list, and an always-present selection echo.

The issue body (#238) is authoritative; its 18 decisions are not repeated here.

## Interface

```python
run_pytest_check(
    markers=None, extra_args=None, env_vars=None, timeout_seconds=None,
    coverage: bool = False,
    coverage_source: Optional[List[str]] = None,  # None = auto-detect from pyproject
    max_modules: int = 10,
)
```

With `coverage=False` the tool behaves exactly as today (same arguments reach
`check_code_with_pytest`).

## Architectural / design changes

1. **`runners.py` is not touched.** Coverage is layered on in the registrar
   (`checker_tools/pytest_tool.py`): it creates its own temp dir, appends the
   coverage flags to the sanitized `extra_args`, adds `COVERAGE_FILE` to
   `env_vars`, and reads the JSON after the run. This is the one deliberate
   deviation from the issue's wording ("the temp dir `run_tests` already
   creates"); the requirement behind it — artifacts outside the repo, `git status`
   clean, JSON kept by `keep_temp_files` — is met.
2. **One new module, `code_checker_pytest/coverage.py`,** holds all coverage
   logic as small pure functions over the coverage JSON dict — no new dataclasses.
3. **`fail_under` is read with `python -c`** in the target interpreter
   (`coverage.Coverage().config.fail_under`), `cwd=project_dir`, uncached. No new
   target script, `target_scripts/` docstring unchanged.
4. **`--cov-fail-under=0` is appended last**, after user `extra_args`, which
   neutralises any target-configured or user-supplied threshold.
5. **pytest-cov availability** is taken from
   `get_environment_info(...).distributions` and refused via
   `context.unavailable_message("pytest-cov")`. `TOOL_MODULES` is not changed; a
   failed probe (fail-open) lets the run proceed.
6. **coverage < 7.6.0** is detected per file (no `functions` key) and degrades to
   file-level ranges with one note line — no up-front version parsing.
7. **`project_config.py`** gains a read-only `addopts` accessor and a
   containment-aware source-only lookup; the existing `where` / `testpaths`
   parsing is extracted into private helpers shared with `get_target_directories`.
8. **`SanitizedArgs`** gains `path_args: list[str]`, filled by the existing path
   detection, so the selection echo can name the paths.
9. **`pytest-cov`** is added to the `dev` extra (for the integration test).

Layering is unchanged: `code_checker_pytest` → `utils`; `checker_tools` →
`code_checker_pytest` + `utils`.

## Files

| Action | Path |
|---|---|
| Modify | `src/mcp_tools_py/utils/project_config.py` |
| Modify | `src/mcp_tools_py/code_checker_pytest/models.py` |
| Modify | `src/mcp_tools_py/code_checker_pytest/utils.py` |
| Create | `src/mcp_tools_py/code_checker_pytest/coverage.py` |
| Modify | `src/mcp_tools_py/checker_tools/pytest_tool.py` |
| Modify | `pyproject.toml` (`dev` extra) |
| Modify | `README.md`, `docs/architecture/architecture.md` |
| Modify | `tests/test_project_config.py` |
| Modify | `tests/test_code_checker_pytest/test_extra_args.py` |
| Create | `tests/test_code_checker_pytest/test_coverage.py` |
| Create | `tests/test_code_checker_pytest/test_coverage_integration.py` |
| Modify | `tests/test_server_params.py` |

## Steps

1. `get_pytest_addopts` accessor — `step_1.md`
2. `resolve_coverage_source` source-only lookup — `step_2.md`
3. `SanitizedArgs.path_args` — `step_3.md`
4. Coverage run plumbing: flags, env, JSON load, `fail_under` read — `step_4.md`
5. Selection echo — `step_5.md`
6. Coverage digest formatter — `step_6.md`
7. Wire into `run_pytest_check`, dev extra, integration test, docs — `step_7.md`

Each step is one commit: tests first, then implementation, then
pylint / pytest / mypy passing and `run_format_code`.
