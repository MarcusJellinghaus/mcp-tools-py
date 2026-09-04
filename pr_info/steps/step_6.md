# Step 6 — `ToolContext`; convert `CheckerTools` and `FormatterTools`

The registrars stop reaching into `ToolServer` and take a frozen value object instead.
This is what lets the last two `ignore_imports` entries go.

**Acceptance criterion closed:** "`lint-imports` and `tach` pass with the six
`ignore_imports` entries removed." Advances "All five registrars take the same argument
type" (step 7 finishes it).

**#229 makes this step materially smaller than planned.** The five `_<tool>_binary`
attributes became one `_tool_binaries: dict[str, str]` (`server.py:108`), so the
five-attribute migration is gone; `ToolServer.tool_unavailable_message`
(`server.py:237-262`) already replaced the nine bespoke error strings, so this step *moves*
one method instead of consolidating nine; and the availability tests are already split into
a package, so whole files can be deleted or rewritten rather than surgery inside a 547-line
module.

## WHERE

**Created**
- `src/mcp_tools_py/utils/tool_context.py`
- `tests/test_tool_context.py`

**Modified**
- `src/mcp_tools_py/server.py` — builds the context; loses `_tool_availability`,
  `_is_tool_available`, `_tool_binaries`, `_script_path` and `tool_unavailable_message`
- `src/mcp_tools_py/checker_tools/__init__.py` and all nine `*_tool.py` modules
- `src/mcp_tools_py/formatter/formatter_tools.py`
- `.importlinter` — delete the last two `ignore_imports` entries
- `tests/test_checker_tools.py` (`:13-54` fixture),
  `tests/test_code_checker_bandit/test_integration.py` (`:11-20`),
  `tests/test_formatter_tools.py`, `tests/conftest.py` (shared `ToolContext` fixture)
- `tests/test_tool_availability/` — `test_check_tool_availability.py` and
  `test_is_tool_available.py` are deleted, `test_unavailable_message.py` moves to
  `tests/test_tool_context.py`, `test_handler_short_circuit.py` and
  `test_resolve_python_executable.py` are rewritten in place
- `tests/test_server_params.py` — patches `_check_tool_availability` and assigns
  `_is_tool_available`; both disappear in this step

## WHAT

```python
# src/mcp_tools_py/utils/tool_context.py

# Derived, not a third copy of the ten-tool taxonomy: step 2 moved TOOL_MODULES
# and TOOL_PACKAGES into utils/environment_info.py as the single home.
CONSOLE_SCRIPT_TOOLS: frozenset[str] = frozenset(
    key for key, module in TOOL_MODULES.items() if module is None
)

@dataclass(frozen=True)
class ToolContext:
    """Everything a tool registrar needs, and nothing about the server."""

    project_dir: Path
    environment: PythonEnvironment
    test_folder: str = "tests"
    keep_temp_files: bool = False
    vulture_whitelist: str = "vulture_whitelist.py"
    check_timeout: int | None = None

    def is_tool_available(self, tool_name: str) -> bool: ...
    def unavailable_message(self, tool_name: str) -> str: ...
    def resolve_timeout(self, tool: ToolName, explicit: int | None = None) -> int: ...
```

Frozen with **no** mutable collaborator: the availability cache lives in
`environment_info.get_environment_info`'s `lru_cache`, keyed by interpreter path. This is
simplification 1 from the summary — decision 20's tension between `frozen=True` and a lazy
cache does not arise.

`CheckerTools.__init__(self, context: ToolContext)` and
`FormatterTools.__init__(self, context: ToolContext)`.

## ALGORITHM

```
is_tool_available(name):
    if name in CONSOLE_SCRIPT_TOOLS:
        return self.environment.binary(name) is not None      # filesystem, free
    return get_environment_info(str(self.environment.interpreter)).importable.get(name, False)

resolve_timeout(tool, explicit):
    return get_check_timeout(str(self.project_dir), tool, explicit, self.check_timeout)
```

`unavailable_message(name)` is **`ToolServer.tool_unavailable_message` moved onto
`ToolContext`**, not a new consolidation: #229 already replaced the nine bespoke strings the
tool modules used to build by hand (`server.py:237-262`) and already maps `lint-imports` to
the `import-linter` distribution through `_TOOL_PACKAGES`. Each tool module's short-circuit
becomes `return context.unavailable_message("ruff")`, and the `TOOL_MODULES` /
`TOOL_PACKAGES` lookups it needs come from `utils/environment_info.py` (step 2's single
home), not from `server`.

Keep both templates: for a console-script tool the message names `environment.bin_dir`, for
an `-m` tool it names the interpreter, and step 2's probe adds the Python version and the
distribution-present-or-not diagnosis.

**Four substrings are the user-facing contract** and must survive verbatim:

| Substring | Asserted at |
|---|---|
| `"<tool> is not available"` | `test_handler_short_circuit.py:36,61,86,219`; `test_unavailable_message.py:29,41,53`; `tests/test_checker_tools.py:200,591,635,679`; `tests/test_formatter_tools.py:318`; `tests/test_code_checker_bandit/test_integration.py:51` |
| `"Restart the server"` | `test_handler_short_circuit.py:37,62,87`; `test_unavailable_message.py:31,44`; `tests/test_code_checker_bandit/test_integration.py:52` |
| `"import-linter is installed"` | `test_unavailable_message.py:54`; `test_check_tool_availability.py:168` |
| **absence** of `"--venv-path"` | `test_unavailable_message.py:33,45` |

The last one rules out the wording step 2 originally proposed — "Ensure
`--python-executable` / `--venv-path` point at the project's environment" fails both
assertions. Name only `--python-executable`; step 2 is written that way.

The diagnostic wording at step 2's `_is_tool_available` warning list contains neither
`"is not available"` nor `"Restart the server"` — that text is the *logger warning* for the
lazy probe. Build the returned message as "`<tool>` is not available …" plus that diagnosis
plus "Restart the server after installing.", so the added diagnostic is a gain and the
contract holds.

`test_unavailable_message.py` (four tests) is the existing pin for all of this. Move it to
`tests/test_tool_context.py` rather than deleting it: the templates it checks are the same,
only their owner changes.

## HOW — `server.py`

```python
self.environment = PythonEnvironment.resolve(python_executable, venv_path)
self.context = ToolContext(
    project_dir=project_dir, environment=self.environment, test_folder=test_folder,
    keep_temp_files=keep_temp_files, vulture_whitelist=vulture_whitelist,
    check_timeout=check_timeout,
)
self._warn_missing_console_scripts()
CheckerTools(self.context).register(self.mcp)
FormatterTools(self.context).register(self.mcp)
```

`_check_tool_availability` becomes `_warn_missing_console_scripts()`: it loops over
`CONSOLE_SCRIPT_TOOLS`, logs the same warnings, and **stores nothing**. Today's startup
warnings are unchanged (decision 14); the five probe-dependent warnings became lazy in
step 2.

Delete `_tool_availability`, `_is_tool_available`, `_tool_binaries`, `_script_path`,
`tool_unavailable_message` and `_resolved_python`. `ToolServer` keeps `resolve_timeout` only
if something outside the registrars still calls it — otherwise delete that too and let
`ToolContext.resolve_timeout` be the single implementation.

Each of those removed names has readers in the test suite, and every one of them must move
in this commit:

| Removed name | Readers | Fix |
|---|---|---|
| `_check_tool_availability` (renamed) | `tests/test_server_params.py:53,105,142,412,747,798` — `patch.object(ToolServer, "_check_tool_availability", return_value={})` | `patch.object` raises `AttributeError` on a missing attribute. Repoint at `_warn_missing_console_scripts` with `return_value=None`; it stores nothing, so the patch is only suppressing startup warnings. |
| `_is_tool_available` | `tests/test_server_params.py:59,109,146,416,501,528,800` — `_server._is_tool_available = lambda tool_name: True  # type: ignore[method-assign]` | The method is gone, so both the assignment and its `type: ignore` are wrong (mypy's `--warn-unused-ignores` flags the latter). Replace with a `ToolContext` whose availability answers `True`: patch `mcp_tools_py.utils.tool_context.get_environment_info` to return an `EnvironmentInfo` marking every probed module importable, from the shared fixture added below. |
| `_resolved_python` | `test_resolve_python_executable.py:32,49,95,113,126`, `test_handler_short_circuit.py:161,193,218`, `test_unavailable_message.py:30,42` and `tests/test_server_params.py:79,84` | `TestResolvePythonExecutable` becomes assertions on `server.environment.interpreter`, which is what step 1 already rewrote most of them to; finish the conversion here. `test_handler_short_circuit.py:161` asserts `call_kwargs.kwargs["python_executable"] == server._resolved_python` — change the right-hand side to `str(server.context.environment.interpreter)`; `:193` and `:218` become `str(server.context.environment.bin_dir)`. `test_server_params.py:79,84` assert `python_executable=` and `venv_bin=` in the `check_code_with_pytest` kwargs — change to `str(_server.context.environment.interpreter)` and `str(_server.context.environment.bin_dir)`, matching what `pytest_tool.py` now passes. `test_unavailable_message.py` moves to `tests/test_tool_context.py` and reads the context instead. |
| `_tool_availability` | `test_check_tool_availability.py` (whole file), `test_is_tool_available.py` (whole file), `test_handler_short_circuit.py:24,49,74,108,146,188,206`; `tests/test_checker_tools.py:22,42,197,588,632,676`; `tests/test_formatter_tools.py:19,23,308` | The dict is gone; availability is `ToolContext.is_tool_available`. Two files are deleted and one rewritten — see the fixture migration below. |
| `_tool_binaries` | `test_check_tool_availability.py:53,68,86,89,114,116,118,133,148,150,188`, `test_is_tool_available.py:73,77`, and the three mock fixtures below | All of them sit in the two files this step deletes, or are covered by the fixture migration. |

## HOW — the nine tool modules

Uniform substitutions, one per module:

| Today | After |
|---|---|
| `server = checker_tools._server` | `context = checker_tools.context` |
| `server._is_tool_available("ruff")` (`ruff_check_tool.py:40`, `ruff_fix_tool.py:41`, `bandit_tool.py:41`, `tach_tool.py:28`, `vulture_tool.py:39`, `lint_imports_tool.py:38`, `pylint_tool.py:38`, `pytest_tool.py:75`, `mypy_tool.py:65`, `formatter_tools.py:73`) | `context.is_tool_available("ruff")` |
| `server._tool_binaries["ruff"]` (`ruff_check_tool.py:62`, `ruff_fix_tool.py:62`, `bandit_tool.py:62`, `tach_tool.py:37`, `vulture_tool.py:64`, `lint_imports_tool.py:43`) | `context.environment.binary("ruff")` |
| `server._resolved_python` (`pylint_tool.py:65`, `pytest_tool.py:102`, `mypy_tool.py:93`, `formatter_tools.py:88`) | `str(context.environment.interpreter)` |
| `os.path.dirname(server._resolved_python)` (`pytest_tool.py:107`, passed as `venv_bin=`) | `str(context.environment.bin_dir)` |
| `server.tool_unavailable_message(key)` | `context.unavailable_message(key)` |
| `server.project_dir` / `.test_folder` / `.keep_temp_files` / `.vulture_whitelist` | same names on `context` |
| `server.resolve_timeout(...)` | `context.resolve_timeout(...)` |

#229 already removed the `assert ... is not None` guards along with the five
`_<tool>_binary` attributes; `_tool_binaries[key]` is now indexed directly after the
availability check. Because `binary()` returns `Path | None`, the index becomes a `None`
check that returns `context.unavailable_message(...)`.

## HOW — `.importlinter`

Delete the last two entries:

```
    mcp_tools_py.checker_tools -> mcp_tools_py.server
    mcp_tools_py.formatter.formatter_tools -> mcp_tools_py.server
```

The whole `ignore_imports =` key goes with them. `ToolServer` was their only remaining
match. Confirm `run_lint_imports_check` reports zero ignored imports and does not error
on an unmatched expression.

## DATA

`ToolContext` is a frozen dataclass of plain values plus one `PythonEnvironment`. It holds
no cache, no subprocess and no reference to the server. `is_tool_available` returns
`bool`; `unavailable_message` returns the user-facing string.

## Tests (write first)

`tests/test_tool_context.py`:

1. `is_tool_available` for a console-script tool is a filesystem answer — create
   `tmp_path/.../ruff(.exe)`, assert `True`; remove it, assert `False`; assert
   `get_environment_info` was never called.
2. `is_tool_available` for an `-m` tool reads the probe — patch
   `mcp_tools_py.utils.tool_context.get_environment_info` and assert both outcomes.
3. `unavailable_message` names the bin dir for a console-script tool and the interpreter
   plus Python version for an `-m` tool; in both cases it contains `"<tool> is not
   available"` and `"Restart the server"` and does **not** contain `"--venv-path"`, and for
   `lint-imports` it says `"import-linter is installed"` — the four substrings tabulated
   under ALGORITHM. These are `test_unavailable_message.py`'s assertions, moved here.
4. `resolve_timeout` delegates to `get_check_timeout` with `check_timeout` as the
   server-level fallback.
5. The dataclass is frozen — assigning to a field raises `FrozenInstanceError`.

**Fixture migration** — these files carry a mock `ToolServer` between them and go red the
moment the registrars change, so they move in this same commit:

- `tests/test_checker_tools.py:13-54` — replace the `MagicMock` server with a real
  `ToolContext` built over a `tmp_path` environment. Availability is controlled by
  creating or omitting binary files and by patching `get_environment_info`, not by writing
  `_tool_availability` (`:22`). `_tool_binaries` (`:34-40`), the stubbed
  `_is_tool_available` (`:42`) and the stubbed `tool_unavailable_message` (`:43-46`) all
  disappear, and so does `server.venv_path` (`:20`), which step 1 already removed from
  production but which a `MagicMock` tolerated silently.
- `tests/test_tool_availability/` — every file here reads state this step deletes. Two are
  deleted, one moves, two are rewritten:

  - **`test_check_tool_availability.py` (9 tests) — delete the file.** Every assertion
    reads `server._tool_availability` or `server._tool_binaries`, and
    `_check_tool_availability` no longer returns a dict. Move what is missing before
    deleting:
    - "binary present / absent" and `test_scripts_found_without_venv_path` (`:170`) are
      `PythonEnvironment.binary()` hit/miss — already covered by
      `tests/test_python_environment.py` tests 8-9.
    - "all five at once" (`test_all_tools_available` `:16`, `test_all_tools_missing` `:36`)
      is `ToolContext.is_tool_available`; parametrize `tests/test_tool_context.py` case 1
      over `CONSOLE_SCRIPT_TOOLS` so the five-name coverage is not lost.
    - `test_startup_warning_matches_handler_message` (`:152`) asserts the startup warning
      *is* the handler's message, `import-linter` naming included. That behaviour has no
      other home: add it to the new startup-warning test below rather than dropping it.
    - The remaining behaviour is that the **server warns at startup**. Add one test in
      `tests/test_server_params.py`: construct a server whose `bin_dir` is an empty
      `tmp_path`, assert `_warn_missing_console_scripts` logs a warning naming each of the
      five tools and matching `context.unavailable_message(...)` (`caplog`), and assert the
      server stores no availability attribute.
  - **`test_is_tool_available.py` — delete the file and move its behaviours to
    `tests/test_tool_context.py`.** After step 2 it holds eight tests, all calling
    `server._is_tool_available(...)` or reading `server._tool_availability`. They map onto
    `ToolContext.is_tool_available`: first call probes; a second call runs no further
    subprocess (assert the patched `get_environment_info` was called once across two
    `is_tool_available` calls — the caching lives in its `lru_cache`, not on the server); a
    console-script tool never probes (case 1); a probe reporting a module not importable
    answers `False`; **a failed or timed-out probe answers `True` and warns** (step 2's
    fail-open policy — this one must not be lost). Fold them into cases 1-2 and one new
    fail-open case rather than adding a near-duplicate class.
  - **`test_unavailable_message.py` (4 tests) — move to `tests/test_tool_context.py`**, with
    `server.tool_unavailable_message(...)` becoming `context.unavailable_message(...)` and
    `server._resolved_python` becoming the context's interpreter. Its four assertions are
    the message contract tabulated under ALGORITHM.
  - `test_handler_short_circuit.py` (7 tests) sets `server._tool_availability` directly at
    `:24,49,74,108,146,188,206`; convert to the `ToolContext` mechanism. `:218` already
    asserts the searched directory appears in the message — keep it, against
    `unavailable_message`. (Review round 5's finding that this line needed a
    `bin_dir`-relative assertion is resolved: #229 wrote it that way.)
  - `test_resolve_python_executable.py` (7 tests): `:32,49,95,113,126` read
    `_resolved_python` and become `server.environment.interpreter` assertions, which is
    what step 1 already rewrote most of them to. Keep the file — it still tests resolution
    order, now `PythonEnvironment.resolve`'s contract as seen through the server. Rename it
    if the class name no longer fits.

  Update each surviving module docstring — they name `_resolve_python_executable` and
  `_check_tool_availability`, neither of which exists after this step.
- `tests/test_server_params.py` — the six `_check_tool_availability` patches and the seven
  `_is_tool_available` assignments listed in the table above, plus `:79,84`. This file is
  not a `ToolContext` fixture holder; it constructs real servers, so it needs the patch
  targets updated rather than a fixture swap.
- `tests/test_code_checker_bandit/test_integration.py:11-25` — same conversion.
- `tests/test_formatter_tools.py:13-31` — the formatter fixture follows `CheckerTools`.

Prefer one shared `ToolContext` fixture (in `tests/conftest.py`) over three near-copies.

## Checks

`run_format_code`, `run_pylint_check`, `run_pytest_check`, `run_mypy_check`,
`run_lint_imports_check` (zero ignored imports now), `run_tach_check`, `run_vulture_check`
(deleted attributes may leave orphaned whitelist entries).

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_6.md`, then implement step 6.
> Write `tests/test_tool_context.py` first — folding in
> `tests/test_tool_availability/test_unavailable_message.py`, so the four message
> substrings stay pinned — then add `utils/tool_context.py`, moving
> `ToolServer.tool_unavailable_message` onto it and deriving `CONSOLE_SCRIPT_TOOLS` from
> `TOOL_MODULES` rather than restating the tool list. Then convert `CheckerTools`, the nine
> `*_tool.py` modules and `FormatterTools` to take a `ToolContext`, strip the corresponding
> state from `server.py`, and migrate the three mock-server fixtures plus every reader of
> the removed names — the table in the step lists them, including
> `tests/test_server_params.py`; they must all move in this commit or pytest goes red. In
> `tests/test_tool_availability/`, delete `test_check_tool_availability.py` and
> `test_is_tool_available.py` — they test methods that no longer exist — after folding the
> behaviours the step names, including the fail-open probe case, into
> `tests/test_tool_context.py` and the new startup-warning test. Delete the last two
> `.importlinter` `ignore_imports` entries and the now-empty `ignore_imports` key. Do not
> touch `RefactoringTools`, `InspectTools` or `UtilityTools` — step 7 owns them. One commit,
> all checks passing.
