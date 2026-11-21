# Step 1 — `--strict-markers` in this repo's pytest config, with regression test

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_1.md`
> exactly as written. Use TDD:
> 1. Write the test first and run it. It must fail: without `--strict-markers`
>    an unregistered marker only warns.
> 2. Then change `pyproject.toml` and run the test again. It must pass.
> 3. Update the vulture comment and `.claude/CLAUDE.md`.
> 4. Run the checks listed below.
>
> Make one commit.

## WHERE

- `tests/test_repo_pytest_config.py` (new)
- `pyproject.toml`, `[tool.pytest.ini_options]`
- `vulture_whitelist.py`, the `_no_outer_tracing` line
- `.claude/CLAUDE.md`, the "Available marker: `integration`" line

## WHAT

### `tests/test_repo_pytest_config.py`

```python
"""Integration test for this repo's own pytest config."""

import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[1]
_UNREGISTERED = "unregistered_probe_marker"


@pytest.fixture(autouse=True)
def _no_outer_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep an outer traced run from leaking into the nested one."""
    monkeypatch.delenv("COVERAGE_PROCESS_CONFIG", raising=False)


def test_unregistered_marker_fails_collection(tmp_path: Path) -> None:
    """A test marked with an unregistered marker fails collection (--strict-markers)."""
```

- Copy the `_no_outer_tracing` fixture verbatim from
  `tests/test_subprocess_tracing.py`.
- Do **not** copy that module's `pytest.importorskip(...)` lines.
- Mark the module, not the single test, with `integration`
  (`pytestmark = ...`), as `tests/test_subprocess_tracing.py` does.

### `pyproject.toml`

```toml
addopts = "-n auto --strict-markers"
```

Use the flag. Do not add a `strict_markers = true` ini key.

### `vulture_whitelist.py`

```python
_no_outer_tracing  # Autouse fixture in tests/test_subprocess_tracing.py and tests/test_repo_pytest_config.py
```

Change the comment only; do not add an entry.

### `.claude/CLAUDE.md`

Insert one sentence directly after the line
`Available marker: \`integration\` (requires external resources).`
For example:

```
New markers must be registered under `[tool.pytest.ini_options] markers` in `pyproject.toml`, or collection fails (`--strict-markers`).
```

## HOW

- The test's subprocess:
  - uses `sys.executable -m pytest` with `check=False`,
    `capture_output=True` and `text=True`, as in
    `tests/test_subprocess_tracing.py`;
  - passes `-c <repo>/pyproject.toml`, which loads this repo's `addopts`;
  - passes `-n 0`, which overrides `-n auto` for speed;
  - passes `-p no:cacheprovider`, so the run writes no cache.
- The temp file lives in `tmp_path`, outside `tests/`, so this repo's
  `tests/conftest.py` is not loaded. There is no root `conftest.py`.

## ALGORITHM

```
test_file = tmp_path / "test_marked.py"
write: "import pytest\n\n\n@pytest.mark.<_UNREGISTERED>\ndef test_marked():\n    pass\n"
result = subprocess.run([sys.executable, "-m", "pytest", "-c", str(_REPO_ROOT / "pyproject.toml"),
                         "-n", "0", "-p", "no:cacheprovider", str(test_file)], ...)
output = result.stdout + result.stderr
assert result.returncode != 0, output
assert f"'{_UNREGISTERED}' not found in `markers` configuration option" in output
```

- Combine stdout and stderr: pytest prints the collection error to stdout.
- Do not assert a specific exit code.

## DATA

- The test returns `None`.
- `result` is a `subprocess.CompletedProcess[str]`.

## Checks (all must pass)

1. `mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto", "-p", "no:cacheprovider", "tests/test_repo_pytest_config.py"])`:
   - It must fail before the `pyproject.toml` edit.
   - It must pass after the edit.
2. `mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"])`: the full
   suite (unit and integration) collects and passes under `--strict-markers`.
3. `mcp__mcp-tools-py__run_pylint_check`, `mcp__mcp-tools-py__run_mypy_check`,
   `mcp__mcp-tools-py__run_ruff_check`.
4. `mcp__mcp-tools-py__run_format_code`, then commit with
   `mcp__mcp-workspace__git_commit`, passing `paths` for the four files above.

## Preconditions

- If the full suite fails to collect because of `--strict-markers` (an
  unregistered marker on a real test), write one line to
  `pr_info/.blocked.txt` and stop.
- If the test still fails after the `pyproject.toml` edit because the expected
  message text differs, write one line to `pr_info/.blocked.txt` and stop.
- If the MCP edit tool refuses `.claude/CLAUDE.md`, write one line to
  `pr_info/.blocked.txt` and stop.

## Commit message

```
test(pytest): add --strict-markers to addopts (#77)
```
