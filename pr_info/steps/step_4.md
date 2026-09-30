# Step 4 — Coverage run plumbing

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_4.md`).
> Implement only this step, TDD: write the tests first, then the code. Run
> pylint, pytest (`-n auto`), mypy and `run_format_code`; all must pass. One commit.

## WHERE

- Create `src/mcp_tools_py/code_checker_pytest/coverage.py`
- Create `tests/test_code_checker_pytest/test_coverage.py`

## WHAT

```python
COVERAGE_JSON = "coverage.json"
COVERAGE_DATA = ".coverage"

def coverage_args(sources: list[str], temp_dir: str) -> tuple[list[str], dict[str, str]]:
    """pytest flags and env vars for one coverage run writing into temp_dir."""

def read_coverage_report(temp_dir: str) -> dict[str, Any] | None:
    """Load the coverage JSON from temp_dir, or None when absent or unparsable."""

def read_fail_under(interpreter: str, project_dir: str) -> float | None:
    """Effective `fail_under` of the project, read in the target interpreter.
    0.0 = none configured; None = could not be read."""
```

## HOW

- Imports: `execute_command` from `mcp_tools_py.utils.subprocess_runner`,
  `PROBE_TIMEOUT_SECONDS` from `mcp_tools_py.utils.environment_info`,
  `read_file` from `mcp_tools_py.utils.file_utils`. Never `mcp_coder_utils`.
- `read_fail_under` runs
  `[interpreter, "-c", "import coverage; print(coverage.Coverage().config.fail_under)"]`
  with **`cwd=project_dir`** (coverage resolves its config relative to cwd) and
  `timeout_seconds=PROBE_TIMEOUT_SECONDS`. Uncached — `fail_under` is per project.
- Module docstring: states that pytest-cov flags are appended after user args so
  `--cov-fail-under=0` wins (decision 13).

## ALGORITHM

```
coverage_args:
  args = [f"--cov={s}" for s in sources]
  args += [f"--cov-report=json:{join(temp_dir, COVERAGE_JSON)}", "--cov-fail-under=0"]
  env = {"COVERAGE_FILE": join(temp_dir, COVERAGE_DATA)}   # file inside the dir: xdist fragments stay inside
  return args, env
read_fail_under:
  r = execute_command(cmd, cwd=project_dir, timeout_seconds=...)
  if r.timed_out or r.execution_error or r.return_code != 0: return None
  try: return float(r.stdout.strip()) except ValueError: return None
```

## DATA

`(["--cov=src", "--cov-report=json:/tmp/x/coverage.json", "--cov-fail-under=0"], {"COVERAGE_FILE": "/tmp/x/.coverage"})`

## Tests (unit, `execute_command` patched)

- `coverage_args`: one `--cov=` per source; `--cov-fail-under=0` is the last arg;
  JSON path and `COVERAGE_FILE` lie inside `temp_dir` and are not `temp_dir` itself
- `read_coverage_report`: valid file → dict; missing / invalid JSON → `None`
- `read_fail_under`: asserts `cwd=project_dir` was passed; `"80.0\n"` → `80.0`;
  non-zero exit, timeout, garbage stdout → `None`
