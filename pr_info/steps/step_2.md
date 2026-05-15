# Step 2 — Split `test_integration_formatting.py` along source-file lines

Reorganise the 814-line single test class into per-source-module test files,
plus a shared `conftest.py`. One commit.

## LLM Prompt

```
Read pr_info/steps/summary.md, then implement Step 2 from
pr_info/steps/step_2.md. Split
tests/test_code_checker_pytest/test_integration_formatting.py into:
- conftest.py (shared fixtures only)
- _helpers.py (project-builder helper functions)
- test_reporting.py (9 tests exercising reporting.py)
- test_runners.py (2 tests exercising runners.py)

Test files import helpers from the sibling `_helpers` module — never
from `conftest`. Delete the original file. Remove both
tests/test_code_checker_pytest/test_integration_formatting.py and the
stale tests/test_code_checker_pytest/test_integration_show_details.py
entries from .large-files-allowlist. If test_reporting.py still exceeds
750 lines after the move, sub-split per the fallback in summary.md.

Run pytest (full suite); ensure the test count matches before/after.
Write the commit message to pr_info/.commit_message.txt — do NOT commit.
```

## WHERE — File paths and module structure

Delete:
- `tests/test_code_checker_pytest/test_integration_formatting.py`

Create:
- `tests/test_code_checker_pytest/conftest.py`
- `tests/test_code_checker_pytest/_helpers.py`
- `tests/test_code_checker_pytest/test_reporting.py`
- `tests/test_code_checker_pytest/test_runners.py`

Modify:
- `.large-files-allowlist` — remove:
  - `tests/test_code_checker_pytest/test_integration_formatting.py`
  - `tests/test_code_checker_pytest/test_integration_show_details.py` (stale, file not in repo)

## WHAT — Test allocation (by current method name)

### → `test_reporting.py` (9 tests; class `TestReporting`)

Tests of formatting / output behaviour from `code_checker_pytest/reporting.py`:

1. `test_focused_debugging_session`
2. `test_large_test_suite_with_failures`
3. `test_specific_test_with_prints`
4. `test_verbose_pytest_with_show_details`
5. `test_no_tests_found_with_show_details`
6. `test_all_tests_pass_with_show_details`
7. `test_collection_errors_with_show_details`
8. `test_output_length_management`
9. `test_clean_temporary_file_handling`

### → `test_runners.py` (2 tests; class `TestRunners`)

Tests of marker filtering / runner-behaviour from `code_checker_pytest/runners.py`:

1. `test_marker_filtering_with_details`
2. `test_performance_validation`

### → `conftest.py` (fixtures only)

Move these fixtures out of the class so any test file in this
directory can use them.

**Fixtures (currently class methods on `TestIntegrationFormatting`):**

```python
@pytest.fixture
def temp_project_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test projects."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def server(temp_project_dir: Path) -> ToolServer:
    """Create a ToolServer instance for testing."""
    return ToolServer(project_dir=temp_project_dir)
```

### → `_helpers.py` (project-builder helpers)

Move these helpers (currently class methods) into a sibling module —
NOT into `conftest.py`. Importing from a conftest file is a pytest
anti-pattern (conftest is intended for fixtures + hooks, picked up
automatically by pytest, not as an importable module).

```python
"""Project-builder helpers for code_checker_pytest integration tests."""

from pathlib import Path


def _create_focused_project(project_dir: Path) -> None: ...
def _create_large_project(project_dir: Path) -> None: ...
def _create_edge_case_project(project_dir: Path) -> None: ...
```

The leading underscore marks them as intra-package test utilities.

## HOW — Integration points

- **Fixtures auto-discovered:** pytest finds `conftest.py` automatically. No `import` in test files.
- **Helpers explicit-import from `_helpers`:** test files use `from tests.test_code_checker_pytest._helpers import _create_focused_project` (or whichever helpers they need). Never import from `conftest.py`.
- **De-classing helpers:** drop the `self` parameter; callsites `self._create_focused_project(temp_project_dir)` become `_create_focused_project(temp_project_dir)`.
- **De-classing fixture access:** test functions take `temp_project_dir` and `server` as parameters directly (already the pattern — no `self.server` usage).
- **Imports per file:** each test file imports only what its tests use (`json`, `time`, `pytest`, `parse_pytest_report`, `CheckerTools`, `ToolServer`, `Path`, etc.) plus the helpers from `_helpers`.
- **Existing helpers `tests/conftest.py`** stays unchanged — it only defines `make_command_result`, which these tests don't use.

## ALGORITHM — Migration procedure

```
1. Create conftest.py with the 2 fixtures (temp_project_dir, server).
2. Create _helpers.py with the 3 helper functions (drop `self`).
3. Copy 9 reporting-bucket tests into test_reporting.py inside `class TestReporting`.
4. Copy 2 runners-bucket tests into test_runners.py inside `class TestRunners`.
5. Replace `self._create_*` → `_create_*` in both files;
   add `from tests.test_code_checker_pytest._helpers import _create_*` to each.
6. Delete test_integration_formatting.py.
7. Remove 2 entries from .large-files-allowlist.
8. Run pytest; if test_reporting.py > 750 lines, apply sub-split fallback.
```

## DATA — Return values and data structures

- No behavioural change — each test still constructs the same synthetic
  `test_results: dict` and asserts on `CheckerTools(server)._format_pytest_result_with_details(...)` return string.
- Test count before == test count after: **11 tests** (9 + 2).
- Helper signatures unchanged except for dropping `self`.

## Sub-split fallback (only if needed)

If `test_reporting.py` exceeds 750 lines after migration, split by source
sub-function:

| New file | Tests |
|---|---|
| `test_reporting_show_details.py` | `test_focused_debugging_session`, `test_specific_test_with_prints`, `test_verbose_pytest_with_show_details`, `test_no_tests_found_with_show_details`, `test_all_tests_pass_with_show_details`, `test_collection_errors_with_show_details` |
| `test_reporting_failed_tests.py` | `test_large_test_suite_with_failures`, `test_clean_temporary_file_handling` |
| `test_reporting_output_length.py` | `test_output_length_management` |

Then delete `test_reporting.py`.

## Verification

```python
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"])    # all pass; count unchanged
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"], markers=["integration"])
mcp__mcp-tools-py__run_pylint_check()
mcp__mcp-tools-py__run_mypy_check(strict=True)
mcp__mcp-tools-py__run_format_code()
```

Confirm `mcp-coder check file-size --max-lines 750`:
- no longer reports the deleted `test_integration_formatting.py`
- no longer reports the dead `test_integration_show_details.py`
- new files all under 750 lines

## Commit message

```
refactor(tests): split test_integration_formatting.py by source mapping

Reorganise the 814-line test_integration_formatting.py into
per-source-module test files:
- conftest.py: shared fixtures (temp_project_dir, server)
- _helpers.py: project-builder helpers (sibling module to avoid the
  pytest anti-pattern of importing from conftest.py)
- test_reporting.py: 9 tests exercising code_checker_pytest/reporting.py
- test_runners.py: 2 tests exercising code_checker_pytest/runners.py

Removes both the original file and the stale
test_integration_show_details.py entry from .large-files-allowlist.

No behaviour change; test count unchanged.
```

Write this message to `pr_info/.commit_message.txt`. Do NOT run `git commit`.
