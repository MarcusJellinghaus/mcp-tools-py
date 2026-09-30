# Step 7 — Wire coverage into `run_pytest_check`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_7.md`).
> Implement only this step, TDD: write the tests first, then the code. Run
> pylint, pytest (`-n auto`, including `-m integration` for the new test), mypy,
> lint-imports and `run_format_code`; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `pyproject.toml` — add `"pytest-cov>=5.0"` to `[project.optional-dependencies] dev`
- `README.md` — three rows in *Pytest Parameters*, plus one short paragraph on
  coverage (`omit` / `# pragma: no cover` for exclusions, pytest-cov needed in
  the project env)
- `docs/architecture/architecture.md` — `code_checker_pytest` and
  `utils/project_config.py` bullets
- `tests/test_server_params.py` — handler tests
- Create `tests/test_pytest_tool_coverage.py` for the integration test.
  (Not `tests/test_checker_tools/`: that package would shadow the existing
  `tests/test_checker_tools.py` and silently drop its tests.)

## WHAT

```python
def run_pytest_check(
    markers: Optional[List[str]] = None,
    extra_args: Optional[List[str]] = None,
    env_vars: Optional[Dict[str, str]] = None,
    timeout_seconds: Optional[int] = None,
    coverage: bool = False,
    coverage_source: Optional[List[str]] = None,
    max_modules: int = 10,
) -> str
```

Docstring: document the three parameters, that the digest is appended, that
the target's `fail_under` is not applied, and that exclusions use coverage's
own `omit` / `# pragma: no cover`.

## HOW

- Imports: `get_environment_info` (`utils.environment_info`),
  `get_pytest_addopts`, `resolve_coverage_source` (`utils.project_config`),
  step 4–6 functions from `code_checker_pytest.coverage`, `tempfile`, `shutil`.
- Refusal: `info = get_environment_info(str(context.environment.interpreter))`;
  if `not info.error and "pytest-cov" not in info.distributions` →
  `return context.unavailable_message("pytest-cov")`. Do **not** touch
  `TOOL_MODULES` or `is_tool_available`.
- `coverage=False`: `check_code_with_pytest` receives exactly today's arguments
  (existing `test_run_pytest_check_parameters` must pass unchanged).
- Temp dir: `tempfile.mkdtemp(prefix="pytest_cov_")`, removed in `finally`
  unless `context.keep_temp_files` (decision 9).

## ALGORITHM

```
if coverage: refuse if pytest-cov missing; sources = resolve_coverage_source(...); if str: return it
sanitized = sanitize_extra_args(...)        # unchanged
if coverage: tmp = mkdtemp(); cov_args, cov_env = coverage_args(sources, tmp)
             args = sanitized.cleaned_args + cov_args; env = {**(env_vars or {}), **cov_env}
             fail_under = read_fail_under(interpreter, project_dir)
test_results = check_code_with_pytest(..., extra_args=args, env_vars=env)
result = formatted reply as today (notes prepended)
if coverage: data = read_coverage_report(tmp)
             digest = format_coverage_digest(data, selection_line(markers, sanitized.cleaned_args,
                 sanitized.path_args, get_pytest_addopts(project_dir)), max_modules, fail_under,
                 tests_failed=failed>0 or error>0) if data else "Coverage report was not produced."
             result = f"{result}\n\n{digest}"                  # appended, never replacing
finally: rmtree(tmp) unless keep_temp_files
```

`get_pytest_addopts` raising `ValueError` on bad TOML is caught by the existing
`except Exception` → error string, like other config errors.

## Tests

`tests/test_server_params.py` (mock `check_code_with_pytest`, patch
`get_environment_info`, `read_fail_under`, `read_coverage_report`):
- pytest-cov absent from `distributions` → unavailable message naming
  `pytest-cov`, `check_code_with_pytest` not called
- probe `error` set → run proceeds
- coverage on: `--cov-fail-under=0` is the last element of `extra_args` passed;
  `COVERAGE_FILE` in `env_vars` alongside the caller's vars
- explicit `coverage_source=["a", "b"]` → `--cov=a` and `--cov=b` in `extra_args`
- `max_modules=3` is forwarded to `format_coverage_digest` (patched)
- `where=["."]` project → error string naming `coverage_source`
- digest appended after the normal reply; failure run contains the warning line
- missing JSON → "Coverage report was not produced."

`tests/test_checker_tools/test_pytest_tool.py` (`@pytest.mark.integration`,
`sys.executable`, skip if `pytest_cov` not importable): tmp project with
`src/pkg/mod.py` (one tested and one untested function), a `pyproject.toml`
without coverage config, and a `.coveragerc` with `[report] fail_under = 99`
(proves a non-pyproject config home is read with the project as `cwd`):
- reply contains the total line, `selection: full suite`, the untested
  function name with its range, and the "not applied" `fail_under` line
- run does not report failure despite `fail_under = 99`
- no `.coverage*` or `coverage.json` created in the project dir
