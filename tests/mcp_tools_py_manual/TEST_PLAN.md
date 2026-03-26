# MCP tools-py Server — Manual Test Plan

## Overview

Manual test plan for all 8 tools exposed by the `mcp-tools-py` MCP server.
Solution-independent — uses a self-contained sample project created during setup.

## Sample Project Structure

```
tests/mcp_tools_py_manual/
├── TEST_PLAN.md                ← this file
├── SAMPLE_PROJECT_FILES.md     ← file contents (used during setup)
├── PROGRESS_TRACKER.md         ← template (copied per run)
├── __init__.py                 ← created during setup
└── sample_project/             ← created during setup
    ├── __init__.py
    ├── models.py               ← User, Order classes + MAX_NAME_LENGTH, DEFAULT_STATUS
    ├── utils.py                ← create_user, is_active, format_user (imports models)
    ├── services.py             ← register_user, place_order (imports models + utils)
    └── tests/
        ├── __init__.py
        ├── test_models.py      ← 4 tests
        ├── test_utils.py       ← 4 tests
        └── test_services.py    ← 3 tests
```

File contents: see [SAMPLE_PROJECT_FILES.md](SAMPLE_PROJECT_FILES.md).

### Design Rationale

- **3 modules with cross-imports**: `services → utils → models` — exercises import rewriting
- **2 classes, 2 constants, 5 functions**: enough symbols to test list/find/rename/move
- **3 test files**: verify that refactoring doesn't break tests
- **No external dependencies**: only stdlib + pytest

---

## Setup

### Entry conditions

1. Ensure the `mcp-tools-py` MCP server is running and accessible
2. Ensure the server's `--project-dir` points to the repository root
3. Verify `mcp-tools-py` is installed in **editable mode** so the server runs the current source.
4. After any source code change, **restart the MCP server** for changes to take effect.

### Create sample project

1. Create `tests/mcp_tools_py_manual/__init__.py` (empty)
2. Create all sample project files from [SAMPLE_PROJECT_FILES.md](SAMPLE_PROJECT_FILES.md):
   - `sample_project/__init__.py`
   - `sample_project/models.py`
   - `sample_project/utils.py`
   - `sample_project/services.py`
   - `sample_project/tests/__init__.py`
   - `sample_project/tests/test_models.py`
   - `sample_project/tests/test_utils.py`
   - `sample_project/tests/test_services.py`
3. Verify tests pass:
   ```
   run_pytest_check(extra_args=["tests/mcp_tools_py_manual/", "-v"])
   ```
4. Copy [PROGRESS_TRACKER.md](PROGRESS_TRACKER.md) to `pr_info/PROGRESS_TRACKER_RUN_<date>.md` for this run

> **Note:** The `sample_project/` directory is checked into git.
> Between mutation tests, delete + recreate it from SAMPLE_PROJECT_FILES.md
> to restore a clean state.

---

## Execution Workflow

### Allowed tools

Only use **MCP tools** and **pre-approved bash commands** (see CLAUDE.md).
Arbitrary bash commands trigger user authorization prompts and interrupt
the flow. When in doubt, prefer an MCP tool over a bash command.

### Timing

Use `tools/get_time.sh` and `tools/get_duration.sh` to measure each test.
Fall back to approximate durations from MCP tool response times if unavailable.

Record in the progress tracker:
- **Run start / Run end / Total duration** in the header
- **Duration** column for each individual test (approximate is fine)

### During execution

- **Before each test**: record start time, then run the test
- **After each test**: record duration, set status to ✅, ❌, or ⏭️
- **On failure**: record the error in the Notes column immediately, then continue
- **On unexpected behavior** (not a failure, but surprising): note it — these become Observations in the report

### After each mutation test (6c, 7c, 8c)

Delete the entire `sample_project/` directory and recreate it from
[SAMPLE_PROJECT_FILES.md](SAMPLE_PROJECT_FILES.md). This ensures a clean
state without relying on git.

### After all tests

1. Generate a status report (see [Status Report](#status-report) section)
2. Clean up:
   - Delete `sample_project/` directory (all files via MCP `delete_this_file`)
   - Delete `tests/mcp_tools_py_manual/__init__.py` (created during setup)
   - Keep run tracker and status report for reference

---

## Test 1: `run_pylint_check`

### 1a — Default run

| Field | Value |
|-------|-------|
| **Call** | `run_pylint_check()` |
| **Expected** | Returns pylint output covering `src/` and `tests/`. No crash. |

### 1b — Scoped to directory

| Field | Value |
|-------|-------|
| **Call** | `run_pylint_check(target_directories=["tests/mcp_tools_py_manual/sample_project"])` |
| **Expected** | Only analyses files in the sample project directory. |

### 1c — Extra args

| Field | Value |
|-------|-------|
| **Call** | `run_pylint_check(extra_args=["--disable=C0114"])` |
| **Expected** | Suppresses `missing-module-docstring`. Other issues (if any) still reported. |

### 1d — Max issues

| Field | Value |
|-------|-------|
| **Call** | `run_pylint_check(max_issues=5)` |
| **Expected** | Shows up to 5 issue types in detail; remaining as summary counts. |

---

## Test 2: `run_pytest_check`

### 2a — Sample project only

| Field | Value |
|-------|-------|
| **Call** | `run_pytest_check(extra_args=["tests/mcp_tools_py_manual/", "-v"])` |
| **Expected** | Runs 11 tests (4 model + 4 utils + 3 services). All pass. |

### 2b — Single file

| Field | Value |
|-------|-------|
| **Call** | `run_pytest_check(extra_args=["tests/mcp_tools_py_manual/sample_project/tests/test_models.py", "-v"])` |
| **Expected** | Runs only the 4 model tests. |

### 2c — Single test function

| Field | Value |
|-------|-------|
| **Call** | `run_pytest_check(extra_args=["tests/mcp_tools_py_manual/sample_project/tests/test_models.py::test_user_creation", "-vvv"])` |
| **Expected** | Runs 1 test with maximum verbosity. |

### 2d — Keyword filter

| Field | Value |
|-------|-------|
| **Call** | `run_pytest_check(extra_args=["tests/mcp_tools_py_manual/", "-k", "order"])` |
| **Expected** | Runs only tests with "order" in the name (test_order_add_item, test_place_order_active, test_place_order_inactive). |

### 2e — With env vars

| Field | Value |
|-------|-------|
| **Call** | `run_pytest_check(extra_args=["tests/mcp_tools_py_manual/", "-v"], env_vars={"DEBUG": "1"})` |
| **Expected** | Tests run with `DEBUG=1` in the environment. All pass. |

---

## Test 3: `run_mypy_check`

### 3a — Strict mode (default)

| Field | Value |
|-------|-------|
| **Call** | `run_mypy_check(target_directories=["tests/mcp_tools_py_manual/sample_project"])` |
| **Expected** | Strict type checking on sample project. Reports any type issues. |

### 3b — Non-strict

| Field | Value |
|-------|-------|
| **Call** | `run_mypy_check(strict=False, target_directories=["tests/mcp_tools_py_manual/sample_project"])` |
| **Expected** | Relaxed checking. Fewer or no errors compared to strict. |

### 3c — Disable specific error codes

| Field | Value |
|-------|-------|
| **Call** | `run_mypy_check(target_directories=["tests/mcp_tools_py_manual/sample_project"], disable_error_codes=["import", "no-untyped-def"])` |
| **Expected** | Those specific error codes suppressed in output. |

### 3d — Follow imports: skip

| Field | Value |
|-------|-------|
| **Call** | `run_mypy_check(target_directories=["tests/mcp_tools_py_manual/sample_project"], follow_imports="skip")` |
| **Expected** | Only checks files in target dir, doesn't follow imports to other packages. |

---

## Test 4: `list_symbols`

### 4a — Models file (classes + constants)

| Field | Value |
|-------|-------|
| **Call** | `list_symbols(file="tests/mcp_tools_py_manual/sample_project/models.py")` |
| **Expected symbols** | `MAX_NAME_LENGTH`, `DEFAULT_STATUS`, `User`, `Order` |

### 4b — Utils file (functions)

| Field | Value |
|-------|-------|
| **Call** | `list_symbols(file="tests/mcp_tools_py_manual/sample_project/utils.py")` |
| **Expected symbols** | `create_user`, `is_active`, `format_user` |

### 4c — Services file

| Field | Value |
|-------|-------|
| **Call** | `list_symbols(file="tests/mcp_tools_py_manual/sample_project/services.py")` |
| **Expected symbols** | `register_user`, `place_order` |

### 4d — Nonexistent file

| Field | Value |
|-------|-------|
| **Call** | `list_symbols(file="tests/mcp_tools_py_manual/sample_project/nonexistent.py")` |
| **Expected** | Error message indicating file not found. |

---

## Test 5: `find_references`

### 5a — Widely-used constant

| Field | Value |
|-------|-------|
| **Call** | `find_references(file="tests/mcp_tools_py_manual/sample_project/models.py", symbol_name="MAX_NAME_LENGTH")` |
| **Expected** | References in: `models.py` (definition), `utils.py` (import + usage), `test_models.py` (import + usage), `test_utils.py` (import + usage) |

### 5b — Class used across modules

| Field | Value |
|-------|-------|
| **Call** | `find_references(file="tests/mcp_tools_py_manual/sample_project/models.py", symbol_name="User")` |
| **Expected** | References in: `models.py`, `utils.py`, `services.py`, `test_models.py`, `test_utils.py`, `test_services.py` |

### 5c — Function with fewer references

| Field | Value |
|-------|-------|
| **Call** | `find_references(file="tests/mcp_tools_py_manual/sample_project/utils.py", symbol_name="format_user")` |
| **Expected** | References in: `utils.py` (definition), `test_utils.py` (import + usage) |

### 5d — Nonexistent symbol

| Field | Value |
|-------|-------|
| **Call** | `find_references(file="tests/mcp_tools_py_manual/sample_project/models.py", symbol_name="DOES_NOT_EXIST")` |
| **Expected** | Error or empty result set. |

---

## Test 6: `rename_symbol`

**Target**: Rename `MAX_NAME_LENGTH` → `NAME_MAX_CHARS` in models.py.

### 6a — Dry run

| Field | Value |
|-------|-------|
| **Call** | `rename_symbol(file="tests/mcp_tools_py_manual/sample_project/models.py", symbol_name="MAX_NAME_LENGTH", new_name="NAME_MAX_CHARS", dry_run=True)` |
| **Expected** | Preview showing planned changes in: `models.py`, `utils.py`, `test_models.py`, `test_utils.py`. No files actually modified. |
| **Verify** | Re-read the file contents — they should be unchanged from SAMPLE_PROJECT_FILES.md. |

### 6b — Apply

| Field | Value |
|-------|-------|
| **Call** | `rename_symbol(file="tests/mcp_tools_py_manual/sample_project/models.py", symbol_name="MAX_NAME_LENGTH", new_name="NAME_MAX_CHARS", dry_run=False)` |
| **Expected** | All occurrences renamed across the project. |
| **Verify** | 1. Check that models.py, utils.py, test_models.py, test_utils.py have changed (contain `NAME_MAX_CHARS`). 2. `run_pytest_check(extra_args=["tests/mcp_tools_py_manual/", "-v"])` — all tests pass. 3. `list_symbols(file="tests/mcp_tools_py_manual/sample_project/models.py")` — shows `NAME_MAX_CHARS`, not `MAX_NAME_LENGTH`. |

### 6c — Teardown

Delete `sample_project/` and recreate from [SAMPLE_PROJECT_FILES.md](SAMPLE_PROJECT_FILES.md).

---

## Test 7: `move_symbol`

**Target**: Move `format_user` from `utils.py` → `services.py`.

### 7a — Dry run

| Field | Value |
|-------|-------|
| **Call** | `move_symbol(source_file="tests/mcp_tools_py_manual/sample_project/utils.py", symbol_name="format_user", dest_file="tests/mcp_tools_py_manual/sample_project/services.py", dry_run=True)` |
| **Expected** | Preview showing: `format_user` removed from utils.py, added to services.py, imports updated in test_utils.py. No files modified. |
| **Verify** | Re-read the file contents — they should be unchanged. |

### 7b — Apply

| Field | Value |
|-------|-------|
| **Call** | `move_symbol(source_file="tests/mcp_tools_py_manual/sample_project/utils.py", symbol_name="format_user", dest_file="tests/mcp_tools_py_manual/sample_project/services.py", dry_run=False)` |
| **Expected** | Symbol moved, imports rewritten. |
| **Verify** | 1. Check that utils.py, services.py, test_utils.py have changed. 2. `list_symbols(file="tests/mcp_tools_py_manual/sample_project/utils.py")` — no longer lists `format_user`. 3. `list_symbols(file="tests/mcp_tools_py_manual/sample_project/services.py")` — now lists `format_user`. 4. `run_pytest_check(extra_args=["tests/mcp_tools_py_manual/", "-v"])` — all tests pass. |

### 7c — Teardown

Delete `sample_project/` and recreate from [SAMPLE_PROJECT_FILES.md](SAMPLE_PROJECT_FILES.md).

---

## Test 8: `move_module`

**Target**: Move `utils.py` into a new `helpers/` package.

### 8a — Dry run

| Field | Value |
|-------|-------|
| **Call** | `move_module(source_module="tests/mcp_tools_py_manual/sample_project/utils.py", dest_package="tests/mcp_tools_py_manual/sample_project/helpers", dry_run=True)` |
| **Expected** | Preview showing: `utils.py` moved to `helpers/utils.py`, `__init__.py` created in `helpers/`, all imports updated in `services.py`, `test_utils.py`. No files modified. |
| **Verify** | Re-read the file contents — they should be unchanged. |

### 8b — Apply

| Field | Value |
|-------|-------|
| **Call** | `move_module(source_module="tests/mcp_tools_py_manual/sample_project/utils.py", dest_package="tests/mcp_tools_py_manual/sample_project/helpers", dry_run=False)` |
| **Expected** | Module relocated, all imports rewritten. |
| **Verify** | 1. Check file moves and import changes. 2. `utils.py` no longer exists at original path. 3. `helpers/utils.py` exists with same content. 4. `services.py` imports from `...helpers.utils` instead of `...utils`. 5. `run_pytest_check(extra_args=["tests/mcp_tools_py_manual/", "-v"])` — all tests pass. |

### 8c — Teardown

Delete `sample_project/` and recreate from [SAMPLE_PROJECT_FILES.md](SAMPLE_PROJECT_FILES.md).

---

## Execution Order

| Phase | Tests | Side effects |
|-------|-------|-------------|
| **0. Setup** | Create files, verify tests, copy tracker | Sample project on disk |
| **1. Read-only** | 1a–1d, 2a–2e, 3a–3d, 4a–4d, 5a–5d | None — safe to run in any order |
| **2. Dry-run mutations** | 6a, 7a, 8a | None — preview only, verify files unchanged. **Run sequentially, not in parallel.** |
| **3. Apply + verify + recreate** | 6b→6c, 7b→7c, 8b→8c | One at a time. Delete + recreate before next. |
| **4. Report** | Generate status report, update tracker | Files written |
| **5. Cleanup** | Delete `sample_project/` + `__init__.py` | Test artifacts removed |

---

## Progress Tracking

1. Before starting, copy [PROGRESS_TRACKER.md](PROGRESS_TRACKER.md) → `pr_info/PROGRESS_TRACKER_RUN_<YYYY-MM-DD>.md`
2. Update the run copy after each test:
   - Set status: ✅ Pass, ❌ Fail, ⏭️ Skipped
   - On **failure**: fill the Notes column with the error message or unexpected output
   - On **unexpected behavior** (test passes but output is surprising): prefix note with `[OBS]` — these become Observations in the report
3. The template tracker is never modified — only run copies are updated

---

## Status Report

After execution, generate `pr_info/STATUS_REPORT_<YYYY-MM-DD>.md` covering:

1. **Run info**: date, executor, mcp-tools-py version, branch, git SHA, run start/end/duration
2. **Summary table**: total / passed / failed / skipped counts, broken down by phase, with phase durations
3. **Per-tool results**: one row per test with result and details
4. **Issues found**: any ❌ from the tracker, with severity (blocker/major/minor) and resolution
5. **Observations**: any `[OBS]` notes from the tracker — performance, output quality, edge cases
6. **Conclusion**: overall verdict (PASS/FAIL) answering:
   - All tools functional?
   - Dry-run mode reliable (no files modified)?
   - Import rewriting correct?
   - Tests pass after mutations?
   - Clean revert possible?

---

## Pass Criteria

- All read-only tools return expected output without errors
- All dry-run calls show correct planned changes and leave no files modified
- All apply calls produce correct changes, and tests still pass afterward
- All teardowns restore the project to its original state
