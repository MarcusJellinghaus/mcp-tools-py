# Summary — Issue #220: Tool availability detection misreports installed tools as missing

## Dependency

**Blocked on #219 (PR #227, open).** #227 rewrites subprocess timeout handling across
`server.py`, `main.py`, all eight `checker_tools/*_tool.py`, `tests/test_checker_tools.py`,
`tests/test_server_params.py`, `README.md` and `docs/architecture/architecture.md`.
Merge #227 first, then rebase this work onto it. The conflicts are mechanical, not
semantic: #219 leaves the availability probe hardcoded, so Decision 6 (plain `30`,
no flag) stays consistent. If #227 has already landed, Step 2 must **preserve**
`resolve_timeout`, which sits immediately after `_is_tool_available`.

## Problem

Tool availability is detected two ways; both key on something other than the
interpreter that will actually run the tool.

- **Lazy probe** (`server.py:214-239`) — pytest, pylint, mypy, black, isort.
  `python -m <tool> --version` at `timeout_seconds=10`. On a slower machine
  pytest's plugin autoload pushes this to ~15s. A timeout sets `execution_error`,
  the predicate reads `False`, and that `False` is cached for the server's whole
  lifetime. The tool is not slow — it is permanently unavailable, and the message
  blames configuration that is already correct.
- **Eager file existence** (`server.py:115-212`) — lint-imports, vulture, ruff,
  bandit, tach. Five copy-pasted 12-line blocks, each gated on `if self.venv_path:`.
  `--venv-path` is optional, so with it unset all five record unavailable
  regardless of what is installed.

## Architectural / design changes

### 1. One source of truth for "where the tools live"

Detection derives the script directory from `_resolved_python` — the interpreter
that will actually be used — in **both** paths. `venv_path` stops participating in
detection entirely. A single private helper `ToolServer._script_path(key)` is the
only place that joins a directory to a tool name and tests for existence, shared by
the eager loop and the lazy fast path.

### 2. A table replaces five copy-pasted blocks and one overloaded string

`tool_name` is currently overloaded as dict key, `python -m` module name **and**
console-script filename. `lint-imports` is where those diverge: module names cannot
contain hyphens, so `python -m lint-imports` is impossible. Today that is masked by
an accident — `lint-imports` is always in `_tool_availability` before
`_is_tool_available` runs, so the probe branch is unreachable for it. The table
makes the absence deliberate:

```python
_TOOL_MODULES: dict[str, Optional[str]] = {
    "pytest": "pytest", "pylint": "pylint", "mypy": "mypy",
    "black": "black", "isort": "isort",
    "lint-imports": None, "vulture": None, "ruff": None,
    "bandit": None, "tach": None,
}
```

`None` means "console script only — file existence is the entire check, no probe
and no fail-open". The console script is named after the key in all ten cases, so
the table needs no separate `script` column.

### 3. Two tool classes, deliberately asymmetric

| | probe group | script group |
|---|---|---|
| tools | pytest, pylint, mypy, black, isort | lint-imports, vulture, ruff, bandit, tach |
| detection | script fast path → `python -m` probe → fail open on timeout | script file existence only |
| when | lazy, on first use (kept from #167) | eager, at startup — it is instant |
| invoked as | `python -m <module>` | the console script path |
| may fail open | yes | **no** |

The script group cannot fail open because detection also *produces the path the
tool is run with*. "Available" with no path on disk would trip
`assert binary is not None` and surface `AssertionError` — worse than the message
being fixed. For them, "available" always implies "we hold a concrete path".

### 4. Fail open on timeout, and cache it

```
timed_out                        → True   (WARNING, cached)
rc == 0 and not execution_error  → True
otherwise                        → False  (cached)
```

Branch order is load-bearing. A timeout also sets `execution_error`, so the
existing `rc == 0 and not execution_error` already excludes timeouts; adding the
fail-open branch after it would leave that branch unreachable — compiling cleanly,
passing the existing tests, and leaving the bug untouched.

Caching the optimistic result bounds the cost at one timeout per tool per server
lifetime. A non-timeout `execution_error` (spawn failure, permission denied) is not
a timeout and still caches `False`.

Probes run with `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` (uniformly — inert for the other
four). It never touches the real run, so `-n auto` and xdist are unaffected.
`execute_command(env=...)` is additive, so `PATH` survives.

### 5. `self._tool_binaries: dict[str, str]` replaces five `_X_binary` attributes

Holds the script group only; the probe group is always invoked as
`python -m <module>`, so entries for it would be written and never read. A loop
cannot assign five distinct attribute names without `setattr`, which mypy strict
and vulture both flag. Presence in the dict means available, so the six
`assert binary is not None` guards disappear.

That invariant has two writers, and both must uphold it: Step 2's fast path (which
records the script it just found for a `module=None` key) and Step 3's eager loop.
The dict is therefore created in `__init__` in Step 2, not Step 3.

### 6. Message construction moves onto the server

Sixteen strings across eleven files name `--venv-path`; after this change every one
would point at a flag that no longer affects the outcome. Six of them are
near-identical, which is exactly why fixing one misdiagnosis is an eleven-file
change today. `ToolServer.tool_unavailable_message(key, package=None)` reduces the
ten tool-module sites to one line each and puts the wording in two templates, so
the next correction is one edit. It also reports **the directory searched** instead
of the current `"N/A"` — when a script tool is unavailable its binary attribute is
always `None`, so today the message reads "ruff is not available at N/A".

### 7. `--venv-path` is soft-deprecated, not removed

It still resolves the interpreter with today's precedence — the `main.py` epilog
advertises a `--venv-path`-only configuration, and ignoring it for resolution would
trade a loud false negative for a quiet one. Only its **detection** and **pytest
`PATH` prepend** roles are dropped. It is hidden from `--help` and logs a
deprecation warning. No hard removal: both `.mcp.json` files pass it and mcp-config
still generates it.

### 8. Validation moves to the resolved interpreter

`--venv-path` currently raises `FileNotFoundError` at startup if its python is
missing; `--python-executable` gets no existence check at all. One check on
whatever `_resolve_python_executable` returns replaces it, naming the flag that
supplied the path. This is a new hard failure for a stale `--python-executable`,
deliberately — a server whose interpreter does not exist cannot run a single tool,
so starting up only defers the same conclusion across fifteen tool messages.
`sys.executable` always exists, so the default configuration is unaffected.

## Simplifications applied (vs. the issue's literal wording)

| | issue text | here | why |
|---|---|---|---|
| descriptor | `key` / `script` / `module` record | `dict[str, Optional[str]]` | `script` equals `key` in all ten rows; the third field would always duplicate the dict key. Decision 7 (`module=None` makes lint-imports deliberate) is fully preserved. |
| detection code | eager loop and lazy fast path each check the filesystem | one shared `_script_path()` | Decision 1 ("derive from `_resolved_python` everywhere") becomes literally one function. |
| messages | 16 strings rewritten in place | 2 templates behind one helper | Decision 9 constrains message *content*, not the number of copies. Cuts the `_tool_binaries` blast radius from 12 source reads to 6. |

One wrinkle the collapse must not flatten: `lint_imports_tool.py:42` names
**import-linter**, the pip package, not the tool. The helper takes an optional
`package` argument used at that one call site.

**Not simplified, on purpose:** the eager/lazy split (#167), the
`module is None → False` guard (unreachable in practice, but it is what makes
lint-imports safe by construction rather than by accident), the `timed_out`-first
predicate order, `_tool_binaries`, the interpreter check, the `--venv-path`
suppression, and the docs.

`os.path.exists` — not `pathlib` — throughout detection. Eight existing tests patch
`mcp_tools_py.server.os.path.exists` (14 patch statements, since six also patch
`mcp_tools_py.server.os.name`); `Path(...).exists()` would silently defeat every one
of them, leaving the tests green while exercising the real filesystem.

## Files created or modified

No new source modules or packages. `server.py` shrinks: the new detection code is
roughly 35 lines against the ~100 it replaces.

### Source — modified

| File | Steps | Change |
|---|---|---|
| `src/mcp_tools_py/server.py` | 1, 2, 3, 4 | interpreter validation; `_TOOL_MODULES`; `_script_path`; `_is_tool_available` rewrite; `_check_tool_availability` loop; `_tool_binaries`; `tool_unavailable_message` |
| `src/mcp_tools_py/main.py` | 6 | `--venv-path` hidden + deprecation warning; epilog example |
| `src/mcp_tools_py/checker_tools/lint_imports_tool.py` | 3, 4 | `_tool_binaries`; message via helper (`package="import-linter"`) |
| `src/mcp_tools_py/checker_tools/vulture_tool.py` | 3, 4 | `_tool_binaries`; message via helper |
| `src/mcp_tools_py/checker_tools/ruff_check_tool.py` | 3, 4 | `_tool_binaries`; message via helper |
| `src/mcp_tools_py/checker_tools/ruff_fix_tool.py` | 3, 4 | `_tool_binaries`; message via helper |
| `src/mcp_tools_py/checker_tools/bandit_tool.py` | 3, 4 | `_tool_binaries`; message via helper |
| `src/mcp_tools_py/checker_tools/tach_tool.py` | 3, 4 | `_tool_binaries`; message via helper |
| `src/mcp_tools_py/checker_tools/mypy_tool.py` | 4 | message via helper |
| `src/mcp_tools_py/checker_tools/pylint_tool.py` | 4 | message via helper |
| `src/mcp_tools_py/checker_tools/pytest_tool.py` | 4, 5 | message via helper; `venv_bin=` call site |
| `src/mcp_tools_py/formatter/formatter_tools.py` | 4 | message via helper |
| `src/mcp_tools_py/code_checker_pytest/runners.py` | 5 | `venv_path` → `venv_bin` in two signatures, two docstrings, log field, comment, `PATH` prepend, positional pass-through |

### Tests — modified

| File | Steps |
|---|---|
| `tests/test_tool_availability.py` | 1, 2, 3, 4 |
| `tests/test_checker_tools.py` | 3, 4 |
| `tests/test_formatter_tools.py` | 4 |
| `tests/test_code_checker_bandit/test_integration.py` | 3, 4 |
| `tests/test_server_params.py` | 5 |
| `tests/test_code_checker/test_runners.py` | 5 |

### Tests — created

| File | Step |
|---|---|
| `tests/test_main_args.py` | 6 |

### Docs — modified

| File | Step |
|---|---|
| `README.md` | 7 |
| `docs/architecture/architecture.md` | 7 |

## Steps

Each step is exactly one commit: tests, implementation, and all checks passing.

| # | Step | Decisions |
|---|---|---|
| 1 | [Validate the resolved interpreter at startup](./step_1.md) | 12 |
| 2 | [Rewrite `_is_tool_available`: fast path, 30s probe, fail open on timeout](./step_2.md) | 1, 3, 4, 5, 6, 7, 13 |
| 3 | [Collapse `_check_tool_availability` into a loop; add `_tool_binaries`](./step_3.md) | 1, 8, 15 |
| 4 | [Centralise the unavailable-tool messages](./step_4.md) | 9 |
| 5 | [pytest `PATH` prepend: `venv_path` → `venv_bin`](./step_5.md) | 10 |
| 6 | [Soft-deprecate `--venv-path`](./step_6.md) | 2, 11 |
| 7 | [Documentation](./step_7.md) | 14 |

Step 2 is the fix for the reported symptom; step 3 is the unreported one. Steps 1-4
touch `server.py` in sequence and must be done in order. Steps 5-7 are independent
of each other once 1-4 have landed.

## Verification per step

```
mcp__mcp-tools-py__run_format_code
mcp__mcp-tools-py__run_pylint_check
mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])
mcp__mcp-tools-py__run_mypy_check
```

## Out of scope

- **mcp-config** (MarcusJellinghaus/mcp-config#56) still emits `--venv-path`
  (`src/mcp_config/servers.py:515-522`) and asserts it in
  `tests/test_config/test_filesystem_venv_fix.py::test_code_checker_keeps_venv_path`.
  The deprecation warning fires on every start until that repo is updated.
- **Non-venv interpreters** still report the five script tools unavailable, because
  they have no `python -m` fallback by construction. Unchanged from today.
- **Fail-open degradation quality.** mypy and pylint already route through
  `check_tool_missing_error`; black/isort surface a raw traceback and pytest fails
  through JSON-report parsing. Worth observing during Step 2; not a blocker, and
  not to be fixed here.
- **Timeout configurability** — #219 owns it. The probe keeps a plain `30`.
