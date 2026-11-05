# Step 10: Add selection identity and the merge command

**Commit:** `feat(coverage): add selection identity and data merging`

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_10.md`. Implement step 10 only: write the tests first, then the code, make pylint, pytest and mypy pass, format, and produce one commit. Also run `tests/test_code_checker_pytest/test_coverage_merge.py`, which the default marker selection skips.

## WHERE

- `src/mcp_tools_py/code_checker_pytest/coverage.py`
- `src/mcp_tools_py/code_checker_pytest/coverage_store.py`
- `tests/test_code_checker_pytest/test_coverage_selection_identity.py` (new)
- `tests/test_code_checker_pytest/test_coverage_merge.py` (new)

## WHAT

In `coverage.py`:

```python
def selection_identity(
    markers: list[str] | None, cleaned_args: list[str], path_args: list[str],
    addopts: str | None, env_vars: dict[str, str] | None,
) -> str: ...
```

In `coverage_store.py`:

```python
def merge_coverage_data(
    interpreter: str, project_dir: str, inputs: list[str], temp_dir: str,
    env_vars: dict[str, str] | None, timeout_seconds: int,
) -> dict[str, Any] | None: ...
```

## HOW

- Extract the effective `-m` and `-k` lookup from `selection_line` into a small helper that returns `(value, from_addopts)`, used by both functions, so they can't disagree. `selection_line`'s output doesn't change.
- `merge_coverage_data` uses `execute_command` from `mcp_tools_py.utils.subprocess_runner`, and `read_coverage_report` on a `merge/` subdirectory of `temp_dir`.
- This step has no callers yet. Step 11 wires it in.

## ALGORITHM

```
identity: m = effective -m, with the markers parameter sorted before joining with " and "
    k = effective -k; paths = sorted(path_args)
    rest = cleaned_args minus -m/-k tokens and their values, minus path_args, minus --cov*; sorted
    env = sha256 of json.dumps(sorted(env_vars.items())) when env_vars, else ""
    return json.dumps([m, k, paths, rest, env])

merge: any input missing -> None
    env = {**(env_vars or {}), "COVERAGE_FILE": merge_dir/.coverage}   # never one of the inputs
    run [interpreter, "-m", "coverage", "combine", "--keep", *inputs]
    run [interpreter, "-m", "coverage", "json", "-o", merge_dir/coverage.json, "--fail-under=0"]
    both with cwd=project_dir, timeout_seconds, env
    timed out, execution error or non-zero -> None
    return read_coverage_report(merge_dir)
```

## DATA

- `selection_identity` returns a JSON string, compared with `==`.
- `merge_coverage_data` returns the merged report, or `None` on any failure.

## TESTS

`test_coverage_selection_identity.py`, a `TestSelectionIdentity` class:

- Same args in a different order give the same identity; markers in a different order too.
- `-m a -k b` differs from `-m b -k a`.
- `--ignore=x`, `--deselect=y` and `--lf` make it distinct.
- `--cov*` args don't.
- An addopts `-m` counts, and a command-line `-m` wins over it.
- Different env values differ, and the identity contains no env value in clear.

`test_coverage_merge.py`:

- `integration`, real data files made with `sys.executable -m coverage run --data-file=...` in `tmp_path`, with `pytest.importorskip("coverage")`:
  - Two runs covering different functions merge to a higher percentage, the report's keys stay relative, and per-function regions survive.
  - The inputs still exist afterwards.
  - A configured `fail_under = 99` doesn't fail the merge.
  - A branch run and a statement run return `None`.
  - `env_vars={"COVERAGE_RCFILE": ...}` is honoured.
- Unit, with `execute_command` patched: a missing input returns `None` without running anything; a timeout, an execution error and a non-zero return code each return `None`; `cwd` and `COVERAGE_FILE` are passed, and `COVERAGE_FILE` isn't one of the inputs.
