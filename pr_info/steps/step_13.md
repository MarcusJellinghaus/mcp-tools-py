# Step 13 — End-to-end integration tests

## LLM prompt
Read `pr_info/steps/summary.md` and this file; issue #293 "Acceptance" and "Testability" define the cases.
Write the tests; fix any defect they reveal in the code of steps 1–12 (no new features). Run pylint, mypy, the
non-integration suite and `markers=["integration"]` for this file. One commit.

## Precondition
pytest-xdist must be importable in the test environment. If it is not, write one line to `pr_info/.blocked.txt`
and stop.

## WHERE
- Create `tests/test_code_checker_pytest/test_integration_report_flags.py`, all tests `@pytest.mark.integration`.

## HOW
- One module-scoped project in `tmp_path_factory` with its own `pyproject.toml` (empty `[tool.pytest.ini_options]`,
  so this repo's `addopts` don't apply). `PYTEST*` env is removed by the root conftest.
- Files: module-level `pytest.skip(allow_module_level=True)` file; `pytestmark = pytest.mark.skip("r")` file with
  two tests; two decorated `@pytest.mark.skip` tests; an xfail; 30 parametrized tests each emitting
  `DeprecationWarning("old")`; a passing test that logs a WARNING; a test with a fixture failing in teardown;
  a `slow` test whose fixture sleeps `time.sleep(0.02)` in setup and teardown and whose body sleeps
  `time.sleep(0.02)` in call, so at least 3 stage entries are above the 0.005 s threshold.
- A conftest adding `--snapshot-update` via `pytest_addoption` (no-op flag).
- Run through the registered `run_pytest_check` (see `test_integration_marker_hint._tool`).

## Cases (about four subprocess runs)
1. `extra_args=["-n", "0", "-svra", "--durations=3"]` → module skip counted, `SKIPPED [2] …: r` without line
   number, decorated skips listed separately, xfail absent, `DeprecationWarning: old — 30×`, log record in the
   passing output, durations section with exactly the `slow` test's 3 entries (setup, call, teardown) and no
   hidden-count line for them, teardown error in its block.
2. `extra_args=["-n", "2"]` → teardown error shown, no `[gw` text in failure blocks.
3. A second project where every file is module-skipped → exit-5 reply keeps "No Tests Found", adds
   `⏭️ Skipped: N` and the reasons.
4. `extra_args=["--snapshot-update", "-n", "0", "-svrw"]` → snapshot note present; `-svrw` works as `-s` + `-rw`:
   the warnings section (`DeprecationWarning: old — 30×`) and the passing test's log record in the passing output,
   no skip-reasons section, and no capture-disabled run (the JSON still has the passing test's output).
