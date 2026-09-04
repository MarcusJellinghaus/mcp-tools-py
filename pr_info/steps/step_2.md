# Step 2 — Probe script and `EnvironmentInfo`

One stdlib-only script, run once under the target interpreter, answers every
fixed-per-run question at once. Replaces up to five lazy `python -m X --version`
subprocesses with zero additional ones.

**Acceptance criteria closed:** "No `python -m <tool> --version` subprocess remains",
"`probe.py` is present in a built wheel", "The new contract fails when `probe.py` imports
a project module".

## WHERE

**Created**
- `src/mcp_tools_py/utils/target_scripts/__init__.py` — package marker, docstring only
- `src/mcp_tools_py/utils/target_scripts/probe.py`
- `src/mcp_tools_py/utils/environment_info.py`
- `tests/test_environment_info.py`

**Modified**
- `.importlinter` — new `forbidden` contract
- `src/mcp_tools_py/server.py` — `_is_tool_available`
- `tests/test_tool_availability.py` — `TestIsToolAvailable` (`:244-347`)

## WHAT — the child

```python
# src/mcp_tools_py/utils/target_scripts/probe.py
"""Describe the interpreter running this script. Stdlib only — see summary.md."""

def _info(module_names: list[str]) -> dict[str, object]: ...
def main(argv: list[str]) -> int: ...
```

Invocation: `<target-python> /abs/path/to/probe.py info pylint pytest mypy black isort`

The module list arrives as argv, not hardcoded (decision 16): the child stays a generic
"describe this environment" script and the list of wrapped tools lives beside the code
that wraps them.

## WHAT — the parent

```python
# src/mcp_tools_py/utils/environment_info.py

PROBED_MODULES: tuple[str, ...] = ("pylint", "pytest", "mypy", "black", "isort")
PROBE_TIMEOUT_SECONDS = 30

@dataclass(frozen=True)
class EnvironmentInfo:
    version: str
    sys_path: tuple[str, ...]
    distributions: Mapping[str, str]
    importable: Mapping[str, bool]
    error: str | None = None

def probe_script_path() -> Path: ...

@lru_cache(maxsize=None)
def get_environment_info(interpreter: str) -> EnvironmentInfo: ...
```

`get_environment_info` **returns** a failure-shaped `EnvironmentInfo` (empty maps,
`error` set) rather than raising, because `lru_cache` does not cache exceptions and
decision 3 requires failures to be cached. `ToolContext` can then stay frozen with no
mutable collaborator.

## ALGORITHM — child

```
names = argv[2:]                                     # argv[1] == "info"
importable = {}
for n in names:
    try:    importable[n] = importlib.util.find_spec(n) is not None
    except Exception: importable[n] = False          # find_spec raises on odd names
dists = {d.metadata["Name"].lower(): d.version for d in importlib.metadata.distributions()
         if d.metadata["Name"]}
json.dump({"version": platform.python_version(), "sys_path": sys.path,
           "distributions": dists, "importable": importable}, sys.stdout)
```

`find_spec` is the availability predicate (decision 15): it asks "can this interpreter
import it?" directly and executes nothing. It drops one narrow check — a tool that
imports but crashes on startup — which is accepted: the tool call then fails with the
real traceback instead of reporting "unavailable", and the five console-script tools
never had that check anyway.

## ALGORITHM — parent

```
get_environment_info(interpreter):
    result = execute_command([interpreter, str(probe_script_path()), "info", *PROBED_MODULES],
                             timeout_seconds=PROBE_TIMEOUT_SECONDS)
    if result.timed_out or result.execution_error or result.return_code != 0:
        return _failed(f"could not probe {interpreter}: <reason, stderr snippet>")
    try:    blob = json.loads(result.stdout)
    except ValueError: return _failed(f"probe of {interpreter} returned unparsable output")
    return EnvironmentInfo(version=blob["version"], sys_path=tuple(blob["sys_path"]),
                           distributions=blob["distributions"], importable=blob["importable"])
```

`probe_script_path()` is `Path(__file__).parent / "target_scripts" / "probe.py"` — an
absolute path, per decision 7.

## HOW — `server.py`

`_is_tool_available` keeps its signature and its cache dict, and stops running
subprocesses:

```python
if tool_name in self._tool_availability:
    return self._tool_availability[tool_name]
info = get_environment_info(self._resolved_python)
available = info.importable.get(tool_name, False)
if not available:
    logger.warning(...)          # see below
self._tool_availability[tool_name] = available
return available
```

Actionable warning text (decision 15) — the distributions map turns a flag problem into a
broken-install diagnosis:

- probe failed → `"cannot describe the environment at <interpreter>: <error>"`
- not importable, distribution present → `"<tool> is not importable by <interpreter>
  (Python <version>), though distribution <tool> <ver> is installed"`
- not importable, no distribution → `"<tool> is not installed in <interpreter> (Python
  <version>). Ensure --python-executable / --venv-path point at the project's
  environment."`

The probe runs on **first use**, not at server start (decision 14): a session that only
calls `sleep` pays nothing, and `tests/test_startup_time.py`'s 2 s budget is unaffected.

## HOW — `.importlinter`

Append:

```ini
[importlinter:contract:target-scripts-stdlib-only]
name = target_scripts import nothing from the project
type = forbidden
source_modules =
    mcp_tools_py.utils.target_scripts.probe
forbidden_modules =
    mcp_tools_py.*
    mcp_tools_py.*.*
    mcp_tools_py.*.*.*
```

Naming an **ancestor** of the source module (`mcp_tools_py`, or `mcp_tools_py.utils`) is a
silent no-op in import-linter — it neither errors nor reports — so the obvious contract
would pass while enforcing nothing. The wildcard form works and self-excludes the source
module.

**Verify the contract actually bites** (this is the acceptance criterion, not the
contract's presence): temporarily add
`from mcp_tools_py.utils.subprocess_runner import execute_command` to `probe.py`, run
`run_lint_imports_check`, confirm the report reads BROKEN and names this contract, then
revert. Say in the commit that this was verified.

## DATA

Probe stdout, one line of JSON:

```json
{"version": "3.11.9", "sys_path": ["..."],
 "distributions": {"pylint": "3.2.0"},
 "importable": {"pylint": true, "pytest": true, "mypy": false}}
```

`prefix` and `is_venv` from the issue's sketch are omitted — nothing consumes them.
`sys_path` stays for #228; `distributions` stays for the error text and #61.

## Tests (write first)

`tests/test_environment_info.py`:

1. Parses a well-formed blob into `EnvironmentInfo` (patch
   `mcp_tools_py.utils.environment_info.execute_command`, use `make_command_result` from
   `tests/conftest.py`).
2. Caches success — two calls, `execute_command` called once.
3. Caches failure — non-zero exit, two calls, called once, `error` is set both times.
4. Timeout → `error` set, no exception.
5. Unparsable stdout → `error` set, no exception.
6. Not invoked until first use — construct a server, assert `execute_command` not called.
7. `probe_script_path()` points at an existing file (this is also the wheel-packaging
   guard for criterion 8).
8. **Real-child smoke test:** run `probe.py info json pytest nosuchmodule_xyz` under
   `sys.executable` and assert `importable == {"json": True, "pytest": True,
   "nosuchmodule_xyz": False}` and that `version` matches `platform.python_version()`.

Every test that touches the cache must call `get_environment_info.cache_clear()` — put it
in an autouse fixture in this module.

`tests/test_tool_availability.py` — `TestIsToolAvailable` (`:244-347`) currently patches
`mcp_tools_py.server.execute_command` and asserts a subprocess was run. Repoint it at
`mcp_tools_py.server.get_environment_info` (or patch `execute_command` inside
`environment_info`) and keep the same four behaviours: first call probes, second call is
cached, an eager console-script tool never probes, a failed probe marks unavailable.

## Checks

`run_format_code`, `run_pylint_check`, `run_pytest_check`, `run_mypy_check`,
`run_lint_imports_check` (the new contract must pass), `run_tach_check`
(`target_scripts` sits under `utils`, adds no dependency edge). `probe.py` lives in `src`
so ruff's `D`/`DOC` rules and mypy strict apply to it — annotate fully and docstring it.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`, then implement step 2.
> Write `tests/test_environment_info.py` first, then `probe.py` (stdlib imports only —
> `json`, `sys`, `platform`, `importlib.util`, `importlib.metadata`), then
> `environment_info.py`, then rewire `server._is_tool_available` and repoint
> `TestIsToolAvailable`. Add the `.importlinter` contract and verify it fails when
> `probe.py` imports a project module, then revert that temporary import. One commit,
> all checks passing. Do not add a `source` subcommand yet — step 3 owns it.
