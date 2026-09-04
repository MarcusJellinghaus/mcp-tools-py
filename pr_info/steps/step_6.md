# Step 6 — `ToolContext`; convert `CheckerTools` and `FormatterTools`

The registrars stop reaching into `ToolServer` and take a frozen value object instead.
This is what lets the last two `ignore_imports` entries go.

**Acceptance criterion closed:** "`lint-imports` and `tach` pass with the six
`ignore_imports` entries removed." Advances "All five registrars take the same argument
type" (step 7 finishes it).

## WHERE

**Created**
- `src/mcp_tools_py/utils/tool_context.py`
- `tests/test_tool_context.py`

**Modified**
- `src/mcp_tools_py/server.py` — builds the context; loses `_tool_availability`,
  `_is_tool_available` and the five `_<tool>_binary` attributes
- `src/mcp_tools_py/checker_tools/__init__.py` and all nine `*_tool.py` modules
- `src/mcp_tools_py/formatter/formatter_tools.py`
- `.importlinter` — delete the last two `ignore_imports` entries
- `tests/test_checker_tools.py` (`:13-45` fixture), `tests/test_tool_availability.py`,
  `tests/test_code_checker_bandit/test_integration.py` (`:11-19`),
  `tests/test_formatter_tools.py`
- `tests/test_server_params.py` — patches `_check_tool_availability` and assigns
  `_is_tool_available`; both disappear in this step

## WHAT

```python
# src/mcp_tools_py/utils/tool_context.py

CONSOLE_SCRIPT_TOOLS: frozenset[str] = frozenset(
    {"lint-imports", "vulture", "ruff", "bandit", "tach"}
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

`unavailable_message(name)` centralises the error text the nine tool modules build by
hand today — for a console-script tool it names `environment.bin_dir`, for an `-m` tool it
uses the probe's version and distributions per step 2. Each tool module's short-circuit
becomes `return context.unavailable_message("ruff")`.

**The message must keep two substrings verbatim: `"<tool> is not available"` and
`"Restart the server"`.** Thirteen assertions across four test files match on them, and
they are the user-facing contract, not incidental wording:

| File | Assertions |
|---|---|
| `tests/test_tool_availability.py` | `:396`, `:397`, `:421`, `:422`, `:446`, `:447`, `:547` |
| `tests/test_checker_tools.py` | `:194`, `:585`, `:629`, `:673` |
| `tests/test_formatter_tools.py` | `:301` |
| `tests/test_code_checker_bandit/test_integration.py` | `:45`, `:46` |

The diagnostic wording at `step_2.md:127-132` (`"<tool> is not installed in <interpreter>
(Python <version>)"`) contains **neither** substring — that text is the *logger warning*
for the lazy probe, and adopting it as the tool's return string turns all thirteen
assertions red. Build the message as "`<tool>` is not available …" plus the step-2
diagnosis (interpreter, Python version, distribution present or not) plus "Restart the
server after installing.", so the added diagnostic is a gain and the contract holds. Only
if a substring is deliberately dropped does the table above become a list of assertions to
rewrite; all four files are already in this step's Modified list either way.

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

Delete `_tool_availability`, `_is_tool_available`, `_resolved_python` and the five
`_<tool>_binary` attributes. `ToolServer` keeps `resolve_timeout` only if something
outside the registrars still calls it — otherwise delete that too and let
`ToolContext.resolve_timeout` be the single implementation.

Each of those removed names has readers in the test suite, and every one of them must move
in this commit:

| Removed name | Readers | Fix |
|---|---|---|
| `_check_tool_availability` (renamed) | `tests/test_server_params.py:52,104,141,411,746,797` — `patch.object(ToolServer, "_check_tool_availability", return_value={})` | `patch.object` raises `AttributeError` on a missing attribute. Repoint at `_warn_missing_console_scripts` with `return_value=None`; it stores nothing, so the patch is only suppressing startup warnings. |
| `_is_tool_available` | `tests/test_server_params.py:58,108,145,415,500,527,799` — `_server._is_tool_available = lambda tool_name: True  # type: ignore[method-assign]` | The method is gone, so both the assignment and its `type: ignore` are wrong (mypy's `--warn-unused-ignores` flags the latter). Replace with a `ToolContext` whose availability answers `True`: patch `mcp_tools_py.utils.tool_context.get_environment_info` to return an `EnvironmentInfo` marking every probed module importable, from the shared fixture added below. |
| `_resolved_python` | `tests/test_tool_availability.py:44,61,90,103` (`TestResolvePythonExecutable`), `tests/test_tool_availability.py:520` (`test_resolved_python_passed_to_pytest_runner`, in `TestToolHandlerShortCircuit`) and `tests/test_server_params.py:78` | `TestResolvePythonExecutable` becomes assertions on `server.environment.interpreter`, which is what step 1 already rewrote most of them to; finish the conversion here and drop the class's dependence on the removed alias. `:520` asserts `call_kwargs.kwargs["python_executable"] == server._resolved_python` — change the right-hand side to `str(server.context.environment.interpreter)`; the test's point (the *resolved* interpreter reaches the runner, not the raw `python_executable` argument) is unchanged, and its name stays accurate enough to keep. `test_server_params.py:78` asserts `python_executable=_server._resolved_python` in the `check_code_with_pytest` kwargs — change to `str(_server.context.environment.interpreter)`, matching what `pytest_tool.py` now passes. |
| `_tool_availability` | `tests/test_tool_availability.py` — `TestCheckToolAvailability` (`:126-235`), `TestIsToolAvailable` (`:267,280,327,347`), `TestToolHandlerShortCircuit` (`:384,409,434,468,505,533`); `tests/test_checker_tools.py:23,40,191,582,626,670`; `tests/test_formatter_tools.py:19,23,291` | The dict is gone; availability is `ToolContext.is_tool_available`. Two classes are deleted and two rewritten — see the fixture migration below. |
| the five `_<tool>_binary` | `tests/test_tool_availability.py:162,175,178,203,205,207,222,234,542`, and the three mock fixtures below | `:542` keeps its assertion against `unavailable_message`; the rest belong to `TestCheckToolAvailability`, which is deleted. Otherwise covered by the fixture migration. |

## HOW — the nine tool modules

Uniform substitutions, one per module:

| Today | After |
|---|---|
| `server = checker_tools._server` | `context = checker_tools.context` |
| `server._is_tool_available("ruff")` | `context.is_tool_available("ruff")` |
| `server._ruff_binary` (and the `assert ... is not None`) | `context.environment.binary("ruff")` |
| `server._resolved_python` | `str(context.environment.interpreter)` |
| `server.venv_path` (`pytest_tool.py:111`) | `context.environment.bin_dir` |
| `server.project_dir` / `.test_folder` / `.keep_temp_files` / `.vulture_whitelist` | same names on `context` |
| `server.resolve_timeout(...)` | `context.resolve_timeout(...)` |

Because `binary()` is existence-checked, the `assert binary is not None` guards
(e.g. `vulture_tool.py:65`) become a `None` check that returns
`context.unavailable_message(...)` — one fewer assertion that can fire in production.

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
   plus Python version for an `-m` tool, and in both cases contains `"<tool> is not
   available"` and `"Restart the server"` — the substrings the thirteen existing
   assertions listed under ALGORITHM match on.
4. `resolve_timeout` delegates to `get_check_timeout` with `check_timeout` as the
   server-level fallback.
5. The dataclass is frozen — assigning to a field raises `FrozenInstanceError`.

**Fixture migration** — these three files carry a mock `ToolServer` between them and go
red the moment the registrars change, so they move in this same commit:

- `tests/test_checker_tools.py:13-45` — replace the `MagicMock` server with a real
  `ToolContext` built over a `tmp_path` environment. Availability is controlled by
  creating or omitting binary files and by patching `get_environment_info`, not by
  writing `_tool_availability`. The five `_*_binary` attributes and `venv_path`
  disappear from the fixture.
- `tests/test_tool_availability.py` — **all four classes in this file read state this step
  deletes.** Two are rewritten in place and two go away:

  - `TestToolHandlerShortCircuit` (`:371-547`) sets `server._tool_availability` directly;
    convert to the same mechanism. `:542` sets `_lint_imports_binary` and asserts the path
    appears in the message — keep that assertion against `unavailable_message`.
  - `TestResolvePythonExecutable` (`:26-103`): `:44`, `:61` and `:90` read
    `_resolved_python`, so they become `server.environment.interpreter` assertions, and
    `:103` becomes `Path(sys.executable)`. Keep the class — it still tests resolution
    order, which is now `PythonEnvironment.resolve`'s contract as seen through the server.
  - **`TestCheckToolAvailability` (`:111-236`, seven tests) — delete the class.** Every
    assertion in it reads `server._tool_availability` (`:126`, `:141`, `:161`, `:165`,
    `:174`, `:176`, `:177`, `:202`, `:204`, `:206`, `:221`, `:233`, `:235`) or one of the
    five `_<tool>_binary` attributes (`:162`, `:175`, `:178`, `:203`, `:205`, `:207`,
    `:222`, `:234`), and `_check_tool_availability` no longer returns a dict. Its subject
    survives in two places, so nothing is lost — but move what is missing before deleting:
    - "binary present / absent" (`test_lint_imports_available_when_binary_exists`,
      `test_lint_imports_unavailable_when_binary_missing`, `test_vulture_available_when_binary_exists`,
      and the two `_when_no_venv` tests step 1 rewrote) is `PythonEnvironment.binary()`
      hit/miss — already covered by `tests/test_python_environment.py` tests 6-8.
    - "all five at once" (`test_all_tools_available`, `test_all_tools_missing`) is
      `ToolContext.is_tool_available`; add a case to `tests/test_tool_context.py` case 1
      parametrized over `CONSOLE_SCRIPT_TOOLS`, so the five-name coverage is not lost.
    - The one behaviour neither covers is that the **server warns at startup**. Add one
      test in `tests/test_server_params.py`: construct a server whose `bin_dir` is an empty
      `tmp_path`, assert `_warn_missing_console_scripts` logs a warning naming each of the
      five tools (`caplog`), and assert the server stores no availability attribute.
  - **`TestIsToolAvailable` (`:244-347`, five tests) — delete the class and move its
    behaviours to `tests/test_tool_context.py`.** All five call `server._is_tool_available(...)`
    (`:264`, `:283`, `:302`, `:324`, `:344`) or read `server._tool_availability`
    (`:267`, `:280`, `:327`, `:347`); step 2 repointed them at `get_environment_info`, and
    this step removes the method they exercise. The four behaviours they assert map onto
    `ToolContext.is_tool_available` one for one: first call probes; a second call runs no
    further subprocess (assert the patched `get_environment_info` was called once across
    two `is_tool_available` calls — the caching now lives in its `lru_cache`, not on the
    server); a console-script tool never probes (case 1); a failed probe answers `False`.
    Fold them into cases 1-2 rather than adding a fifth near-duplicate class.

  Update the module docstring at `:1` — it names `_resolve_python_executable` and
  `_check_tool_availability`, neither of which exists after this step.
- `tests/test_server_params.py` — the six `_check_tool_availability` patches and the seven
  `_is_tool_available` assignments listed in the table above. This file is not a
  `ToolContext` fixture holder; it constructs real servers, so it needs the patch targets
  updated rather than a fixture swap.
- `tests/test_code_checker_bandit/test_integration.py:11-19` — same conversion.
- `tests/test_formatter_tools.py` — the formatter fixture follows `CheckerTools`.

Prefer one shared `ToolContext` fixture (in `tests/conftest.py`) over three near-copies.

## Checks

`run_format_code`, `run_pylint_check`, `run_pytest_check`, `run_mypy_check`,
`run_lint_imports_check` (zero ignored imports now), `run_tach_check`, `run_vulture_check`
(deleted attributes may leave orphaned whitelist entries).

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_6.md`, then implement step 6.
> Write `tests/test_tool_context.py` first — including the assertion that
> `unavailable_message` keeps the substrings `"<tool> is not available"` and
> `"Restart the server"` — then add `utils/tool_context.py`, then convert
> `CheckerTools`, the nine `*_tool.py` modules and `FormatterTools` to take a
> `ToolContext`, then strip the corresponding state from `server.py`, then migrate the
> three mock-server fixtures and fix every reader of the removed names — the table in
> the step lists them, including `tests/test_server_params.py` and
> `TestResolvePythonExecutable`; they must all move in this commit or pytest goes red.
> In `tests/test_tool_availability.py`, delete `TestCheckToolAvailability` and
> `TestIsToolAvailable` — they test methods that no longer exist — after folding the
> behaviours the step names into `tests/test_tool_context.py` and the new startup-warning
> test.
> Delete
> the last two `.importlinter` `ignore_imports` entries and the now-empty `ignore_imports`
> key. Do not touch `RefactoringTools`, `InspectTools` or `UtilityTools` — step 7 owns
> them. One commit, all checks passing.
