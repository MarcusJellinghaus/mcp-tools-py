# Step 12: Enable subprocess tracing in this repo

**Commit:** `chore(coverage): trace subprocesses in this repo`

This step is independent of the others.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_12.md`. Implement step 12 only: write the test change first, then the configuration, make pylint, pytest and mypy pass, format, and produce one commit.

## WHERE

- `pyproject.toml`
- `tests/test_startup_time.py`
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

None.

## DATA

No new data structures.

## TESTS

- `test_server_startup_within_budget` still runs without tracing. Add a test that sets `COVERAGE_PROCESS_CONFIG` with `monkeypatch.setenv` and checks that calling the test function raises `pytest.skip.Exception`, with `_measure_startup_seconds` patched so it never spawns anything.

## Verify with a traced run

Run the full suite traced: `run_pytest_check(coverage=True, extra_args=["-n", "auto"], max_modules=0)`.

- The zero-coverage list must not include `rope_cli.py` or `probe.py`.
- `test_server_startup_within_budget` must be skipped.
- Merge tests inherit `COVERAGE_PROCESS_CONFIG` in this run. If `test_coverage_merge.py` or `test_pytest_tool_combine.py` fails only here, remove the variable in those tests with `monkeypatch.delenv("COVERAGE_PROCESS_CONFIG", raising=False)`.

If the installed `coverage` is older than 7.10, or `rope_cli.py` or `probe.py` still appears in the zero-coverage list after the steps above, write one line to `pr_info/.blocked.txt` and stop.
