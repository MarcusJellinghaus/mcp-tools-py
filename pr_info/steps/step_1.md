# Step 1 — Split `src/mcp_tools_py/checker_tools.py` into a package

Convert the 893-line single-file module into a `checker_tools/` package with
one module per MCP tool. One commit.

## LLM Prompt

```
Read pr_info/steps/summary.md, then implement Step 1 from
pr_info/steps/step_1.md. Convert src/mcp_tools_py/checker_tools.py
into a src/mcp_tools_py/checker_tools/ package — one *_tool.py module
per MCP tool, each exposing a free `register(mcp, server)` function.
Re-export `CheckerTools` from __init__.py so existing imports continue
to work. Co-locate private formatter helpers with their sole callers.
Remove `src/mcp_tools_py/checker_tools.py` from .large-files-allowlist.
Run lint-imports, pytest, pylint, and mypy --strict; fix any issues.
Then write the commit message to pr_info/.commit_message.txt — do NOT commit.
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
    """Registers all checker MCP tools on a server."""

    def __init__(self, server: "ToolServer") -> None:
        self._server = server

    def register(self, mcp: "FastMCPProtocol") -> None:
        pylint_tool.register(mcp, self._server)
        pytest_tool.register(mcp, self._server)
        mypy_tool.register(mcp, self._server)
        lint_imports_tool.register(mcp, self._server)
        vulture_tool.register(mcp, self._server)
        ruff_check_tool.register(mcp, self._server)
        ruff_fix_tool.register(mcp, self._server)
        bandit_tool.register(mcp, self._server)
        tach_tool.register(mcp, self._server)


__all__ = ["CheckerTools"]
```

### `checker_tools/<name>_tool.py` (uniform shape)

Each module exposes exactly one public symbol:

```python
def register(mcp: "FastMCPProtocol", server: "ToolServer") -> None: ...
```

Private helpers (formatters, logging) stay module-level with `_` prefix and
are imported by no one outside the module.

### Formatter helper placement (sole callers)

| Helper | Source location now | New home |
|---|---|---|
| `_format_pylint_result` | `CheckerTools._format_pylint_result` | `pylint_tool.py` (module-level) |
| `_format_pytest_result_with_details` | `CheckerTools._format_pytest_result_with_details` | `pytest_tool.py` (module-level) |
| `_format_mypy_result` | `CheckerTools._format_mypy_result` | `mypy_tool.py` (module-level) |

## HOW — Integration points

- **MCP tool decoration:** the `@mcp.tool()` and `@log_function_call` decorators stay on the inner function defined inside `register()`. The decorated function is registered with the MCP server as a side-effect of decoration; `register()` returns `None`.
- **Server access:** `register(mcp, server)` receives `server` and the inner tool function closes over it (replacing `self._server` from the class form).
- **Type-only imports:** `from mcp_tools_py.server import FastMCPProtocol, ToolServer` stays under `if TYPE_CHECKING:` in every `*_tool.py` to satisfy the layered architecture and avoid runtime cycles.
- **Existing carve-out covers the new package:** `.importlinter` has `mcp_tools_py.checker_tools -> mcp_tools_py.server` ignored — package-scoped, no change needed.
- **Caller imports unchanged:** all 6 callers use `from mcp_tools_py.checker_tools import CheckerTools` which resolves through the new `__init__.py`.

## ALGORITHM — Core pattern for each `*_tool.py`

```
def register(mcp, server):
    @mcp.tool()
    @log_function_call
    def run_<tool>_check(<params>) -> str:
        if not server._is_tool_available("<tool>"): return <unavailable_msg>
        resolved = resolve_target_directories(...) if applicable
        try:
            log start; result = call_impl(...); log done
            return _format_<tool>_result(result)  # if applicable
        except Exception as e:
            log error; return <error_msg> or raise
```

## DATA — Return values and data structures

- **Public:** `CheckerTools` class — unchanged external behaviour. `from mcp_tools_py.checker_tools import CheckerTools` still works.
- **Per-tool:** each `register(mcp, server)` returns `None`. Side-effect is `@mcp.tool()` registration.
- **Tool functions:** all return `str` (the MCP tool contract). No structural change to return values vs. current implementation — pure code-motion refactor.

## Verification

Run before commit:

```python
mcp__mcp-tools-py__run_lint_imports_check()                       # must PASS
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto"])    # no test failures
mcp__mcp-tools-py__run_pylint_check()
mcp__mcp-tools-py__run_mypy_check(strict=True)
mcp__mcp-tools-py__run_format_code()                              # black + isort
```

Then verify `mcp-coder check file-size --max-lines 750` no longer flags the
deleted `checker_tools.py` as missing-but-allowlisted and reports each new
`*_tool.py` is well under 750 lines (target ~80–150 lines per file).

## Commit message

```
refactor(checker_tools): split into per-tool modules

Convert checker_tools.py (893 lines) into a checker_tools/ package
with one module per MCP tool. Each *_tool.py exposes a free
register(mcp, server) function; CheckerTools orchestrates dispatch.
Private formatter helpers move next to their sole callers.

Public import `from mcp_tools_py.checker_tools import CheckerTools`
is preserved via __init__.py. No caller changes needed.

Removes checker_tools.py from .large-files-allowlist.
```

Write this message to `pr_info/.commit_message.txt`. Do NOT run `git commit`.
