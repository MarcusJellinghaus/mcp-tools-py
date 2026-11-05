# Step 12: Enable subprocess tracing in this repo

**Commit:** `chore(coverage): trace subprocesses in this repo`

The configuration is independent of the other steps. The new integration test uses `tests/_coverage_project.py` (step 8) and the zero-coverage list (step 6), so this step stays last.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_12.md`. Implement step 12 only: write the test change first, then the configuration, make pylint, pytest and mypy pass, format, and produce one commit. Also run `tests/test_subprocess_tracing.py`, which the default marker selection skips.

## WHERE

- `pyproject.toml`
- `tests/test_startup_time.py`
- `tests/test_subprocess_tracing.py` (new)
- `README.md`

## WHAT

`pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
    ...
    # patch = ["subprocess"] below needs 7.10; older versions only warn and don't trace
    "coverage>=7.10",
]

[tool.coverage.run]
patch = ["subprocess"]
```

`.github/workflows/ci.yml` doesn't change.

## HOW

`tests/test_startup_time.py`: first lines of `test_server_startup_within_budget`:

```python
if "COVERAGE_PROCESS_CONFIG" in os.environ:
    pytest.skip("Subprocess tracing inflates startup time; the untraced CI job enforces the budget.")
```

The check is in the test body, and it doesn't use `Coverage.current()`, because plain `--cov` also sets that.

`README.md`, in the Coverage paragraph: coverage doesn't trace subprocesses by default, and a target project can enable it with `[tool.coverage.run] patch = ["subprocess"]`, which needs coverage 7.10 or later.

## ALGORITHM

```
project(tmp_path, traced):
    src/pkg/__init__.py and src/pkg/covered.py, plus copies of the real rope_cli.py and probe.py, all directly in src/pkg/
    a test that imports pkg.covered, so src/pkg/ doesn't collapse into one row and each file keeps its own row
    and spawns both copies with subprocess.run(check=False):
        [sys.executable, "-m", "pkg.rope_cli"] with PYTHONPATH=src, [sys.executable, <path>/probe.py, "info"]
    pyproject.toml, with [tool.coverage.run] patch = ["subprocess"] only when traced

nested startup run: [sys.executable, "-m", "pytest",
    "tests/test_startup_time.py::test_server_startup_within_budget", "-m", "integration",
    "--cov=src/mcp_tools_py/utils/target_scripts", "--cov-report=", "-n", "0", "-p", "no:cacheprovider"]
    cwd = this repo's root, COVERAGE_FILE under tmp_path, COVERAGE_PROCESS_CONFIG removed
```

## DATA

No new data structures.

## TESTS

`tests/test_startup_time.py`:

- `test_server_startup_within_budget` still runs without tracing: with `COVERAGE_PROCESS_CONFIG` removed by `monkeypatch.delenv` and `_measure_startup_seconds` patched to return `0.0`, calling the test function doesn't skip.
- With `COVERAGE_PROCESS_CONFIG` set by `monkeypatch.setenv`, and `_measure_startup_seconds` patched so it never spawns anything, calling the test function raises `pytest.skip.Exception`.

`tests/test_subprocess_tracing.py`, `integration`, with `pytest.importorskip("pytest_cov")` and `pytest.importorskip("coverage", minversion="7.10")`. Each test removes `COVERAGE_PROCESS_CONFIG` with `monkeypatch.delenv(..., raising=False)`, so an outer traced run doesn't leak into the nested one:

- This repo's `pyproject.toml`, read with `tomllib`, has `"subprocess"` in `[tool.coverage.run] patch`. This ties the project below to this repo's setting.
- Traced project, run through `run_pytest_check(coverage=True)` via `tests/_coverage_project.py`: neither `rope_cli.py` nor `probe.py` appears in the zero-coverage section of the digest. Check that section only, because a traced file can still appear in the gap ranking.
- The same project without the setting: both appear in the zero-coverage list, so the test above can fail.
- The nested startup run from this repo's root, which uses this repo's `pyproject.toml`, exits 0 and reports `1 skipped`.

If the installed `coverage` is older than 7.10, or `rope_cli.py` or `probe.py` still appears in the traced project's zero-coverage list after the steps above, write one line to `pr_info/.blocked.txt` and stop.
