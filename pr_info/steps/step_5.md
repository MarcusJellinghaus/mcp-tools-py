# Step 5 — Move `FastMCPProtocol` and `ToolDecorator` out of `server.py`

Purely mechanical, and required before `ToolContext`: removing `ToolServer` alone would
leave fourteen `tools -> server` back-edges in place, so the `ignore_imports` entries
could not be deleted (decision 9).

**Acceptance criterion advanced:** four of the six `ignore_imports` entries go.

## WHERE

**Created**
- `src/mcp_tools_py/utils/mcp_protocols.py`

**Modified**
- `src/mcp_tools_py/server.py` — protocols removed, imported back for `self.mcp`
- Fourteen importers (all `TYPE_CHECKING` blocks):
  - `checker_tools/__init__.py`
  - `checker_tools/{pylint,pytest,mypy,ruff_check,ruff_fix,bandit,vulture,tach,lint_imports}_tool.py`
  - `formatter/formatter_tools.py`
  - `refactoring/__init__.py`
  - `utility_tools.py`
  - `inspect_library.py`
- `.importlinter` — delete four `ignore_imports` entries

## WHAT

```python
# src/mcp_tools_py/utils/mcp_protocols.py
"""Structural types for the subset of FastMCP this server uses."""

T = TypeVar("T")

class ToolDecorator(Protocol):
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]: ...

class FastMCPProtocol(Protocol):
    def tool(self) -> ToolDecorator: ...
    def run(self) -> None: ...
```

Moved verbatim from `server.py:19-39`, docstrings included.

## HOW

Every importer changes exactly one line:

```python
# before
from mcp_tools_py.server import FastMCPProtocol
# after
from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol
```

Two of the fourteen — `checker_tools/__init__.py:26` and
`formatter/formatter_tools.py:16` — import `FastMCPProtocol, ToolServer` together. They
keep the `ToolServer` half from `mcp_tools_py.server`; step 6 removes it.

`server.py` keeps `from mcp_tools_py.utils.mcp_protocols import FastMCPProtocol` for the
`self.mcp: FastMCPProtocol` annotation.

`mcp_tools_py/utils/__init__.py` needs no re-export — importers use the full path,
consistent with `utils.project_config` and `utils.subprocess_runner` usage elsewhere.

## `.importlinter`

Delete exactly these four lines from the `layers` contract:

```
    mcp_tools_py.checker_tools.** -> mcp_tools_py.server
    mcp_tools_py.refactoring -> mcp_tools_py.server
    mcp_tools_py.utility_tools -> mcp_tools_py.server
    mcp_tools_py.inspect_library -> mcp_tools_py.server
```

Keep `mcp_tools_py.checker_tools -> mcp_tools_py.server` and
`mcp_tools_py.formatter.formatter_tools -> mcp_tools_py.server` — those two still match
the `ToolServer` imports, and step 6 deletes them.

`unmatched_ignore_imports_alerting` defaults to `error` and `.importlinter` does not
override it, so an expression matching nothing aborts the run with "No matches for ignored
import". That is why the deletions happen here rather than all together at the end
(decision 26). Confirm with `run_lint_imports_check` that the report now says "10 ignored
imports" rather than 14.

## DATA

None — no runtime behaviour changes.

## `tach.toml`

No edit needed in this step: tach does not see `TYPE_CHECKING` imports, which is why it
passes today despite the fourteen back-edges import-linter reports. `inspect_library`
already gained `mcp_tools_py.utils` in step 3; `utility_tools` gets it in step 7.

`lint-imports` is the only guard for this step — tach will not catch a regression here.

## Tests

No new tests. This step is verified by the existing suite plus `lint-imports`:

- `run_pytest_check` — everything still imports and registers.
- `run_mypy_check` — the protocol types still resolve at every use site.
- `run_lint_imports_check` — must pass with four entries gone, and must not report an
  unmatched expression.

If any test imports `FastMCPProtocol` from `mcp_tools_py.server`, repoint it. Check
`tests/test_shim_reexports.py` and `tests/test_refactoring/test_lazy_imports.py`, which
assert on module import structure.

## Checks

`run_format_code`, `run_pylint_check`, `run_pytest_check`, `run_mypy_check`,
`run_lint_imports_check`, `run_tach_check`.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_5.md`, then implement step 5.
> Move `T`, `ToolDecorator` and `FastMCPProtocol` verbatim from `server.py` into
> `src/mcp_tools_py/utils/mcp_protocols.py`, repoint all fourteen `TYPE_CHECKING`
> importers, and delete the four named `ignore_imports` entries — not the other two.
> Behaviour must not change; no new tests. Verify with `run_lint_imports_check` that the
> contract passes and reports 10 ignored imports, not 14 and not an unmatched-expression
> error. One commit, all checks passing.
