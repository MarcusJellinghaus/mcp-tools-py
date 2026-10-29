# Step 6: xdist integration test and README

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_6.md`. Add the integration test, run it with `markers=["integration"]`, and confirm it passes. Then update `README.md`. Run pylint, mypy and pytest (`-n auto`, all tests), make sure all of them pass, run `run_format_code`, then make one commit.

## Precondition

The test must produce the xdist abort. If `check_code_with_pytest` does not return `ERROR` with "Different tests were collected" in `verdict.problems` for the project below, write one line to `pr_info/.blocked.txt` and stop.

## WHERE

- New: `tests/test_code_checker_pytest/test_integration_xdist_collection.py`, modelled on `test_integration_show_output.py`.
- `README.md`: the note around line 74.

## WHAT

```python
@pytest.mark.integration
def test_xdist_collection_mismatch_is_error(tmp_path: Path) -> None
```

## ALGORITHM

```text
pytest.importorskip("xdist")
write tmp_path/tests/test_now.py:
    from datetime import datetime; import pytest
    @pytest.mark.parametrize("value", [str(datetime.now())])
    def test_now(value): assert value
result = check_code_with_pytest(str(tmp_path), python_executable=sys.executable, extra_args=["-n", "2"], timeout_seconds=120)
assert result["verdict"].status is RunStatus.ERROR
assert any("Different tests were collected" in p for p in result["verdict"].problems)
```

## README

1. Replace the line "Parallel test execution is enabled by default using pytest-xdist (`-n auto`)." with: "The tool never adds `-n`. Tests run in parallel only when you pass `-n` or the project's `addopts` sets it. `-n 0` disables pytest-xdist."
2. Add a short paragraph on run outcomes:
   - Only a verified pass reads "Pytest check completed."
   - Test failures show the failure details.
   - A run that errored, including a non-zero exit with no failing tests or an xdist collection mismatch, reads "Pytest run reported an error." with the exit code and problems.
   - A run that collected tests but reported no outcomes reads "… Not verified."

## DATA

There is no code change in this step.
