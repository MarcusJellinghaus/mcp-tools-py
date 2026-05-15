# Step 1 — Split `src/mcp_tools_py/checker_tools.py` into a package

Convert the 893-line single-file module into a `checker_tools/` package with
one module per MCP tool. One commit.

## LLM Prompt

```
Read pr_info/steps/summary.md, then implement Step 1 from
pr_info/steps/step_1.md. Convert src/mcp_tools_py/checker_tools.py
into a src/mcp_tools_py/checker_tools/ package — one *_tool.py module
per MCP tool, each exposing a free `register(mcp, checker_tools)`
function. Re-export `CheckerTools` from __init__.py so existing
imports continue to work. Keep `_format_pylint_result`,
`_format_pytest_result_with_details`, and `_format_mypy_result` as
methods on `CheckerTools` in __init__.py (40+ existing test call
sites must remain untouched); register closures call them via the
passed-in `checker_tools` instance. Migrate every
`patch("mcp_tools_py.checker_tools.<symbol>", ...)` site in the test
suite to its new submodule namespace (full list below). Remove
`src/mcp_tools_py/checker_tools.py` from .large-files-allowlist. Run
lint-imports, pytest, pylint, and mypy --strict; fix any issues.
Verify the test count is unchanged before/after. Then write the
commit message to pr_info/.commit_message.txt — do NOT commit.
```

## WHERE — File paths and module structure

Delete:
- `src/mcp_tools_py/checker_tools.py`

Create the package:

```
src/mcp_tools_py/checker_tools/
├── __init__.py            # CheckerTools orchestrator
├── pylint_tool.py
├── pytest_tool.py
├── mypy_tool.py
├── lint_imports_tool.py
├── vulture_tool.py
├── ruff_check_tool.py
├── ruff_fix_tool.py
├── bandit_tool.py
└── tach_tool.py
```

Modify:
- `.large-files-allowlist` — remove the line `src/mcp_tools_py/checker_tools.py`
- `tests/test_checker_tools.py` — retarget `patch("mcp_tools_py.checker_tools.<symbol>", ...)` sites (see Decision 2 inventory below)
- `tests/test_server_params.py` — retarget 13 `check_code_with_pytest` patches + `create_prompt_for_failed_tests`, `get_pylint_prompt`, `resolve_target_directories` patches
- `tests/test_tool_availability.py` — retarget 2 `check_code_with_pytest` patches
- `tests/test_code_checker_bandit/test_integration.py` — retarget `run_bandit_check_impl` and `resolve_target_directories` patches

### Patch-site retargeting inventory (Decision 2)

After the split, `patch("mcp_tools_py.checker_tools.<symbol>", ...)`
must target the **submodule** where `<symbol>` is looked up at call
time — i.e. the `*_tool.py` that has `from … import <symbol>`. Run
`mcp__mcp-workspace__search_files(pattern='mcp_tools_py\\.checker_tools\\.', glob='tests/**/*.py')`
to confirm the full inventory before editing.

| Symbol | New patch path |
|---|---|
| `check_code_with_pytest` | `mcp_tools_py.checker_tools.pytest_tool.check_code_with_pytest` |
| `create_prompt_for_failed_tests` | `mcp_tools_py.checker_tools.pytest_tool.create_prompt_for_failed_tests` |
| `get_pylint_prompt` | `mcp_tools_py.checker_tools.pylint_tool.get_pylint_prompt` |
| `get_mypy_prompt` | `mcp_tools_py.checker_tools.mypy_tool.get_mypy_prompt` |
| `run_vulture` | `mcp_tools_py.checker_tools.vulture_tool.run_vulture` |
| `run_ruff_check_impl` | `mcp_tools_py.checker_tools.ruff_check_tool.run_ruff_check_impl` |
| `run_ruff_fix_impl` | `mcp_tools_py.checker_tools.ruff_fix_tool.run_ruff_fix_impl` |
| `run_tach` | `mcp_tools_py.checker_tools.tach_tool.run_tach` |
| `run_bandit_check_impl` | `mcp_tools_py.checker_tools.bandit_tool.run_bandit_check_impl` |
| `resolve_target_directories` | the owning `*_tool` submodule for that test's call chain (pylint, mypy, vulture, ruff_check, ruff_fix, tach, bandit) |

Known sites to migrate (from current search; the implementer must
re-run the search to catch any drift):

- `tests/test_server_params.py`: 13 `check_code_with_pytest` sites
  (lines 30, 205, 238, 267, 296, 324, 358, 424, 570, 623, 644), 4
  `create_prompt_for_failed_tests` sites (lines 298, 326, 360, 426),
  2 `get_pylint_prompt` sites (lines 468, 495), 2
  `resolve_target_directories` sites (lines 471, 498).
- `tests/test_tool_availability.py`: 2 `check_code_with_pytest`
  sites (lines 454, 486).
- `tests/test_checker_tools.py`: 1 `create_prompt_for_failed_tests`
  (line 138); 3 `run_vulture` (195, 215, 235); 1 `get_pylint_prompt`
  (281); 1 `get_mypy_prompt` (313); 1 `run_ruff_check_impl` (385);
  1 `run_ruff_fix_impl` (429); 1 `run_tach` (472); and 11
  `resolve_target_directories` (199, 219, 239, 277, 295, 309, 327,
  341, 360, 389, 404, 433, 448) — retarget each to the owning
  `*_tool` submodule per the test under it.
- `tests/test_code_checker_bandit/test_integration.py`: 3
  `run_bandit_check_impl` (78, 107, 130) + 3
  `resolve_target_directories` (74, 103, 126) → both retarget to
  `mcp_tools_py.checker_tools.bandit_tool.<symbol>`.

The `_format_*` test call sites (40+ in `test_checker_tools.py`,
`test_server_params.py`, `test_final_validation.py`,
`test_reporting.py`/`test_runners.py`) are NOT patches — they call
methods on `CheckerTools(server)` instances. They stay untouched
because the helpers remain on `CheckerTools` (Decision 1).

## WHAT — Main functions with signatures

### `checker_tools/__init__.py`

```python
"""CheckerTools orchestrator. Public API: from mcp_tools_py.checker_tools import CheckerTools."""

from typing import TYPE_CHECKING

from mcp_tools_py.checker_tools import (
    bandit_tool,
    lint_imports_tool,
    mypy_tool,
    pylint_tool,
    pytest_tool,
    ruff_check_tool,
    ruff_fix_tool,
    tach_tool,
    vulture_tool,
)

if TYPE_CHECKING:
    from mcp_tools_py.server import FastMCPProtocol, ToolServer


class CheckerTools:
    """Registers all checker MCP tools on a server and owns shared formatters."""

    def __init__(self, server: "ToolServer") -> None:
        self._server = server

    def register(self, mcp: "FastMCPProtocol") -> None:
        pylint_tool.register(mcp, self)
        pytest_tool.register(mcp, self)
        mypy_tool.register(mcp, self)
        lint_imports_tool.register(mcp, self)
        vulture_tool.register(mcp, self)
        ruff_check_tool.register(mcp, self)
        ruff_fix_tool.register(mcp, self)
        bandit_tool.register(mcp, self)
        tach_tool.register(mcp, self)

    # --- shared formatter helpers (moved verbatim from the old module) ---

    def _format_pylint_result(self, prompt: str | None) -> str:
        """Return the pylint prompt unchanged or the no-issues message."""
        # body unchanged from current implementation

    def _format_mypy_result(self, prompt: str | None) -> str:
        """Return the mypy prompt unchanged or the no-issues message."""
        # body unchanged from current implementation

    def _format_pytest_result_with_details(
        self,
        test_results: dict,
        return_code: int,
        show_details: bool,
    ) -> str:
        """Format pytest results, optionally including failure details."""
        # body unchanged from current implementation


__all__ = ["CheckerTools"]
```

These three `_format_*` methods are kept identical (signature + body)
to the current `checker_tools.py` implementation. The 40+ existing
test sites that call them on `CheckerTools` instances therefore need
no changes.

### `checker_tools/<name>_tool.py` (uniform shape)

Each module exposes exactly one public symbol:

```python
def register(mcp: "FastMCPProtocol", checker_tools: "CheckerTools") -> None: ...
```

The closure inside `register()` accesses the server as
`checker_tools._server` and the shared formatter helpers as
`checker_tools._format_pylint_result(...)` /
`checker_tools._format_mypy_result(...)` /
`checker_tools._format_pytest_result_with_details(...)`. Tool-local
helpers (if any) stay module-level with a `_` prefix and are not
imported by anyone outside the module.

## HOW — Integration points

- **MCP tool decoration:** the `@mcp.tool()` and `@log_function_call` decorators stay on the inner function defined inside `register()`. The decorated function is registered with the MCP server as a side-effect of decoration; `register()` returns `None`.
- **Server + formatter access:** `register(mcp, checker_tools)` receives the orchestrator instance. The inner tool function closes over it to reach the server (`checker_tools._server`) and the shared formatters (`checker_tools._format_*`).
- **Type-only imports:** `from mcp_tools_py.checker_tools import CheckerTools` (for the parameter annotation) and `from mcp_tools_py.server import FastMCPProtocol` stay under `if TYPE_CHECKING:` in every `*_tool.py` to satisfy the layered architecture and avoid runtime cycles.
- **Existing carve-out covers the new package:** `.importlinter` has `mcp_tools_py.checker_tools -> mcp_tools_py.server` ignored — package-scoped, no change needed.
- **Caller imports unchanged:** `from mcp_tools_py.checker_tools import CheckerTools` continues to resolve through the new `__init__.py`. Patch sites for impl functions (e.g. `check_code_with_pytest`) DO change — see the patch-site retargeting inventory above.

## ALGORITHM — Core pattern for each `*_tool.py`

```
def register(mcp, checker_tools):
    server = checker_tools._server  # captured once for closure use
    @mcp.tool()
    @log_function_call
    def run_<tool>_check(<params>) -> str:
        if not server._is_tool_available("<tool>"): return <unavailable_msg>
        resolved = resolve_target_directories(...) if applicable
        try:
            log start; result = call_impl(...); log done
            # for pylint/mypy/pytest: delegate to the orchestrator's method
            return checker_tools._format_<tool>_result(result)
        except Exception as e:
            log error; return <error_msg> or raise
```

Tools without a formatter helper (lint_imports, vulture, ruff_check,
ruff_fix, bandit, tach) simply return the impl result string and do
not touch `checker_tools._format_*`.

## DATA — Return values and data structures

- **Public:** `CheckerTools` class — unchanged external behaviour. `from mcp_tools_py.checker_tools import CheckerTools` still works. The three `_format_*` instance methods are preserved on the class (signatures + bodies identical to current `checker_tools.py`).
- **Per-tool:** each `register(mcp, checker_tools)` returns `None`. Side-effect is `@mcp.tool()` registration.
- **Tool functions:** all return `str` (the MCP tool contract). No structural change to return values vs. current implementation — pure code-motion refactor.

## Verification

Capture the pytest collection count before starting, then run the
checks below:

```python
# Baseline: collect-only count before any edits
mcp__mcp-tools-py__run_pytest_check(extra_args=["--collect-only", "-q"])
# ... do the refactor ...
mcp__mcp-tools-py__run_lint_imports_check()                       # must PASS
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"])    # no test failures
mcp__mcp-tools-py__run_pytest_check(extra_args=["--collect-only", "-q"])  # count == baseline
mcp__mcp-tools-py__run_pylint_check()
mcp__mcp-tools-py__run_mypy_check(strict=True)
mcp__mcp-tools-py__run_format_code()                              # black + isort
```

**Test-count sanity check:** the pytest collection count after the
refactor MUST equal the count before. No test loss is acceptable —
this is a pure code-motion + patch-site retargeting refactor.

Then verify `mcp-coder check file-size --max-lines 750` no longer flags the
deleted `checker_tools.py` as missing-but-allowlisted and reports each new
`*_tool.py` is well under 750 lines (target ~80–150 lines per file).

## Commit message

```
refactor(checker_tools): split into per-tool modules

Convert checker_tools.py (893 lines) into a checker_tools/ package
with one module per MCP tool. Each *_tool.py exposes a free
register(mcp, checker_tools) function; CheckerTools orchestrates
dispatch and continues to own the shared `_format_pylint_result`,
`_format_mypy_result`, and `_format_pytest_result_with_details`
helpers (preserves 40+ existing test call sites).

Retargets `patch("mcp_tools_py.checker_tools.<symbol>", ...)` sites
across tests/test_checker_tools.py, tests/test_server_params.py,
tests/test_tool_availability.py, and
tests/test_code_checker_bandit/test_integration.py to the new
per-submodule namespaces. Public import
`from mcp_tools_py.checker_tools import CheckerTools` unchanged.

Removes checker_tools.py from .large-files-allowlist.
```

Write this message to `pr_info/.commit_message.txt`. Do NOT run `git commit`.
