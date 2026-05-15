# Issue #201 — Split `checker_tools.py` and `test_integration_formatting.py`

## Goal

Two source files were added to `.large-files-allowlist` (commit `33964dc`) to
unblock the file-size CI check. This refactor removes the need for those
allowlist entries by splitting both files into properly-scoped modules.

Ships as **one PR with two commits** (one commit per refactor).

## Scope

| File | Lines | Action |
|------|-------|--------|
| `src/mcp_tools_py/checker_tools.py` | 893 | Split into `checker_tools/` package, one `*_tool.py` per MCP tool |
| `tests/test_code_checker_pytest/test_integration_formatting.py` | 814 | Split by source mapping (reporting/runners), helpers + fixtures → `conftest.py` |
| `.large-files-allowlist` | — | Remove 3 entries (the two above + stale `test_integration_show_details.py`) |

## Architectural / design changes

### Package layout (Commit 1)

`src/mcp_tools_py/checker_tools.py` → `src/mcp_tools_py/checker_tools/` package:

```
src/mcp_tools_py/checker_tools/
├── __init__.py            # exports CheckerTools orchestrator
├── pylint_tool.py         # register(mcp, server) + _format_pylint_result
├── pytest_tool.py         # register(mcp, server) + _format_pytest_result_with_details
├── mypy_tool.py           # register(mcp, server) + _format_mypy_result
├── lint_imports_tool.py   # register(mcp, server)
├── vulture_tool.py        # register(mcp, server)
├── ruff_check_tool.py     # register(mcp, server)
├── ruff_fix_tool.py       # register(mcp, server)
├── bandit_tool.py         # register(mcp, server)
└── tach_tool.py           # register(mcp, server)
```

### Per-tool entry point

Each `*_tool.py` exposes a module-level free function:

```python
def register(mcp: "FastMCPProtocol", server: "ToolServer") -> None: ...
```

`CheckerTools.register()` (in `__init__.py`) dispatches to each tool's
`register` function. This drops the `self._server` plumbing of the
old `_register_*` methods.

### Why `_tool` suffix

Required to avoid shadowing pip package names (`pytest`, `mypy`, `bandit`,
`pylint`) when modules sit inside `checker_tools/`. Without the suffix,
`from mcp_tools_py.checker_tools import pytest` would clash with `import pytest`.

### Why `formatter_tools.py` is NOT the model

`FormatterTools` lives inside `formatter/` alongside its implementation
modules — that mixes layers. This refactor keeps registration logically
above the `code_checker_*` implementation layer.

### Private formatter helpers

`_format_pylint_result`, `_format_pytest_result_with_details`, and
`_format_mypy_result` each have exactly **one caller**. Co-locate each
with its sole caller inside its matching `*_tool.py` as a private
module-level function. No shared formatters module.

### Layer isolation (no `.importlinter` change)

The existing carve-out

    mcp_tools_py.checker_tools -> mcp_tools_py.server

is package-scoped, so converting `checker_tools.py` to `checker_tools/`
keeps the layered-architecture contract working without changes. Verified
via `lint-imports` after Commit 1.

### Test reorganisation (Commit 2)

`tests/test_code_checker_pytest/test_integration_formatting.py` → split by
which source module each test exercises:

```
tests/test_code_checker_pytest/
├── conftest.py          # NEW — shared fixtures (temp_project_dir, server)
│                        #       + helpers (_create_focused_project,
│                        #         _create_large_project, _create_edge_case_project)
├── test_reporting.py    # NEW — 9 tests exercising reporting.py
├── test_runners.py      # NEW — 2 tests exercising runners.py
├── test_extra_args.py        # unchanged
└── test_integration_env.py   # unchanged
```

Sub-split fallback: if `test_reporting.py` exceeds 750 lines after move,
split by source sub-function into `test_reporting_show_details.py`,
`test_reporting_failed_tests.py`, `test_reporting_output_length.py`.
Projected size after conftest extraction is ~600 lines, so sub-split is
unlikely to be triggered.

## Files created or modified

### Commit 1

**Created:**
- `src/mcp_tools_py/checker_tools/__init__.py`
- `src/mcp_tools_py/checker_tools/pylint_tool.py`
- `src/mcp_tools_py/checker_tools/pytest_tool.py`
- `src/mcp_tools_py/checker_tools/mypy_tool.py`
- `src/mcp_tools_py/checker_tools/lint_imports_tool.py`
- `src/mcp_tools_py/checker_tools/vulture_tool.py`
- `src/mcp_tools_py/checker_tools/ruff_check_tool.py`
- `src/mcp_tools_py/checker_tools/ruff_fix_tool.py`
- `src/mcp_tools_py/checker_tools/bandit_tool.py`
- `src/mcp_tools_py/checker_tools/tach_tool.py`

**Deleted:**
- `src/mcp_tools_py/checker_tools.py`

**Modified:**
- `.large-files-allowlist` — remove `src/mcp_tools_py/checker_tools.py`

**Unchanged (callers still work via `__init__.py` re-export):**
- `src/mcp_tools_py/server.py`
- `tests/test_checker_tools.py`
- `tests/test_server_params.py`
- `tests/test_final_validation.py`
- `tests/test_code_checker_bandit/test_integration.py`

### Commit 2

**Created:**
- `tests/test_code_checker_pytest/conftest.py`
- `tests/test_code_checker_pytest/test_reporting.py`
- `tests/test_code_checker_pytest/test_runners.py`

**Deleted:**
- `tests/test_code_checker_pytest/test_integration_formatting.py`

**Modified:**
- `.large-files-allowlist` — remove `tests/test_code_checker_pytest/test_integration_formatting.py` and stale `tests/test_code_checker_pytest/test_integration_show_details.py`

## Verification

Both commits must pass before pushing:

- `mcp__mcp-tools-py__run_lint_imports_check` — layered architecture intact
- `mcp__mcp-tools-py__run_pytest_check` (`-n auto`) — no test count regression
- `mcp__mcp-tools-py__run_pylint_check`
- `mcp__mcp-tools-py__run_mypy_check` (`strict=True`)
- `mcp-coder check file-size --max-lines 750` — no entries needed for refactored files

## Out of scope

The 5 other stale allowlist entries (`server.py`, `data_files.py`,
`subprocess_runner.py`, `test_server_params.py`, `test_subprocess_runner.py`)
are not addressed here — they belong in a separate chore.
