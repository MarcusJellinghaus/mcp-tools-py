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
- `tests/test_target_scripts_contract.py` — the contract-bites test (criterion 9)
- `tests/test_packaging.py` — the wheel-contents test (criterion 8)

**Modified**
- `.importlinter` — new `forbidden` contract
- `pyproject.toml` — add `"build>=1.0"` to the `dev` extra (see criterion 8 below)
- `src/mcp_tools_py/server.py` — `_is_tool_available`; `PROBE_TIMEOUT_SECONDS`,
  `_TOOL_MODULES` and `_TOOL_PACKAGES` (`:47,51-65`) move to `environment_info.py` and are
  imported back; the `execute_command` import goes with `_is_tool_available` (this was its
  last use, so vulture flags it otherwise — see step 1's dead-import note)
- `tests/test_tool_availability/test_is_tool_available.py` (11 tests, 265 lines) — three
  tests are deleted, two invert, the rest repoint
- `tests/test_tool_availability/test_resolve_python_executable.py` and
  `test_handler_short_circuit.py` — the `patch("mcp_tools_py.server.execute_command")`
  sites outside `TestIsToolAvailable`

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

PROBE_TIMEOUT_SECONDS = 30                       # moved from server.py:47

TOOL_MODULES: dict[str, str | None] = {...}      # moved from server.py:51-65
TOOL_PACKAGES: dict[str, str] = {"lint-imports": "import-linter"}

PROBED_MODULES: tuple[str, ...] = tuple(m for m in TOOL_MODULES.values() if m)

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

**One home for the ten-tool taxonomy.** #229 introduced `PROBE_TIMEOUT_SECONDS`,
`_TOOL_MODULES` and `_TOOL_PACKAGES` in `server.py`; this step would otherwise add a second
copy here and step 6 a third (`CONSOLE_SCRIPT_TOOLS` in `tool_context.py`). Move the three
into `environment_info.py`, drop the leading underscore since they are now cross-module, and
derive everything else from them — `PROBED_MODULES` above, and in step 6
`CONSOLE_SCRIPT_TOOLS = frozenset(k for k, v in TOOL_MODULES.items() if v is None)`.
`server.py` imports them back; its three read sites (`:160`, `:203`, `:249-250`) change name
only. This also removes the risk of `PROBED_MODULES` drifting from the real call sites.

`get_environment_info` **returns** a failure-shaped `EnvironmentInfo` rather than raising,
because `lru_cache` does not cache exceptions and decision 3 requires failures to be cached.
`ToolContext` can then stay frozen with no mutable collaborator. See "Failure is fail-open"
below for what that shape says about availability.

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

### Failure is fail-open

`_failed(reason)` returns
`EnvironmentInfo(version="", sys_path=(), distributions={}, importable={m: True for m in PROBED_MODULES}, error=reason)`.

A probe that fails or times out therefore reports all five module tools **available**, with
a logged warning, so each call proceeds and surfaces the real error. This preserves #229's
policy: `server._is_tool_available` (`server.py:186-235`) has a 30 s timeout that fails
open, pinned by
`tests/test_tool_availability/test_is_tool_available.py:101`
(`test_timeout_fails_open_and_caches`). Failing closed would be a regression the old code
did not have — one slow probe would make all five tools vanish at once, where today each
fails open independently.

"The probe failed" and "the probe succeeded and says pytest is not importable" are
different answers: only the second reports unavailable.

## HOW — `server.py`

`_is_tool_available` keeps its signature and its cache dict, and stops running
subprocesses:

```python
if tool_name in self._tool_availability:
    return self._tool_availability[tool_name]
if TOOL_MODULES.get(tool_name) is None:      # console-script-only tool
    available = self.environment.binary(tool_name) is not None
else:
    info = get_environment_info(self._resolved_python)
    available = info.importable.get(tool_name, False)
    if info.error:
        logger.warning(...)      # fail-open: available stays True
    elif not available:
        logger.warning(...)      # see below
self._tool_availability[tool_name] = available
return available
```

**The console-script branch is load-bearing, not leftover.** `PROBED_MODULES` never carries
a console-script name, so without it `info.importable.get("lint-imports", False)` answers
`False` for all five of them. It is also what `test_is_tool_available.py:82`
(`test_script_only_tool_never_probes`) pins: that test deletes the cache entry, then
asserts the answer is `False` (`:98`) **and** that no probe ran (`:99`). The test is kept
below with only its patch target changed, so the branch has to be here. Step 6's
`ToolContext.is_tool_available` has the same branch.

Actionable warning text (decision 15) — the distributions map turns a flag problem into a
broken-install diagnosis:

- probe failed → `"cannot describe the environment at <interpreter>: <error>. Assuming
  <tool> is available."`
- not importable, distribution present → `"<tool> is not importable by <interpreter>
  (Python <version>), though distribution <tool> <ver> is installed"`
- not importable, no distribution → `"<tool> is not installed in <interpreter> (Python
  <version>). Ensure --python-executable points at the project's environment."`

**Name only `--python-executable`.** `tests/test_tool_availability/test_unavailable_message.py:33`
and `:45` assert `"--venv-path" not in message`, and step 6 builds the user-facing message
from this diagnosis.

The probe runs on **first use**, not at server start (decision 14): a session that only
calls `sleep` pays nothing, and `tests/test_startup_time.py`'s 2 s budget is unaffected.

### #229 behaviours that need no carry-over

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` (`server.py:215`) becomes moot: it existed because the
  probe *ran* `python -m pytest --version`. `find_spec` locates without executing.
- Version logging (`server.py:230`) is preserved through the probe blob's `distributions`
  map — issue decision 15 already relies on it.
- The console-script *fast path for module tools* (`server.py:202-207`) becomes moot: it
  saved a per-tool subprocess, and the probe now runs once for all five. The
  console-script-**only** branch at `:208-210` is a different thing and stays — see the
  sketch above.

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

**The contract must be proven to bite, automatically.** The acceptance criterion is "the
new contract fails when `probe.py` imports a project module" — the contract's mere
presence is not it, and decision 19 records that the obvious spelling passes while
enforcing nothing. A manual add-run-revert leaves no evidence in CI, so this is a test:

`tests/test_target_scripts_contract.py`, two cases, both `@pytest.mark.integration`
(they shell out to `lint-imports`):

```
build a miniature package under tmp_path:
    fakepkg/__init__.py
    fakepkg/utils/__init__.py
    fakepkg/utils/helper.py                       # the "project module"
    fakepkg/utils/target_scripts/__init__.py
    fakepkg/utils/target_scripts/probe.py         # content differs per case
write tmp_path/.importlinter with the same contract shape, root_package = fakepkg
run execute_command(["lint-imports", "--config", str(tmp_path / ".importlinter")],
                    cwd=str(tmp_path))
```

1. `probe.py` imports nothing → exit 0, report says KEPT. This is the case that catches
   the silent no-op: a contract that enforces nothing also passes here, so case 2 is what
   distinguishes them.
2. `probe.py` contains `from fakepkg.utils.helper import thing` → non-zero exit, report
   says BROKEN and names the contract.

Use `lint-imports` from `PythonEnvironment.binary("lint-imports")` if available and
`pytest.skip` otherwise, per the knowledge base's skip-don't-fake rule.

The fixture mirrors the real layout — source module three levels under the root package,
forbidden modules given as wildcards — so it pins the wildcard form itself, which is the
part decision 19 found fragile. Keep it in sync with `.importlinter` by construction: the
test reads the real contract's `forbidden_modules` lines from `.importlinter` and
substitutes `mcp_tools_py` → `fakepkg`, so a later edit to the real contract flows into
the fixture instead of silently diverging.

## DATA

Probe stdout, one line of JSON:

```json
{"version": "3.11.9", "sys_path": ["..."],
 "distributions": {"pylint": "3.2.0"},
 "importable": {"pylint": true, "pytest": true, "mypy": false}}
```

`prefix` and `is_venv` from the issue's sketch are omitted — nothing consumes them.
`sys_path` stays for #228; `distributions` stays for the error text and #61.

`sys_path` is the one field kept with **no** production consumer, so the same reasoning
that drops `prefix` and `is_venv` puts vulture on it: an unread frozen-dataclass field is
reported as `unused variable 'sys_path' (60% confidence)`, exactly the repo's threshold
(`vulture ... --min-confidence 60`, `ci.yml:154`). The parser's
`sys_path=tuple(blob["sys_path"])` is a write, not a read. Test 1 below is its reader.

## Tests (write first)

`tests/test_environment_info.py`:

1. Parses a well-formed blob into `EnvironmentInfo` (patch
   `mcp_tools_py.utils.environment_info.execute_command`, use `make_command_result` from
   `tests/conftest.py`). Assert on **`info.sys_path` as an attribute**, not by comparing
   the whole dataclass: dataclass equality is generated code and does not count as a read,
   so an equality-only test leaves vulture flagging the field (see DATA above).
2. Caches success — two calls, `execute_command` called once.
3. Caches failure — non-zero exit, two calls, called once, `error` is set both times.
4. Timeout → `error` set, no exception.
5. Unparsable stdout → `error` set, no exception.
   Each of 3-5 also asserts the fail-open shape: every name in `PROBED_MODULES` reads
   `True` in `importable`.
6. Not invoked until first use — construct a server, assert `execute_command` not called.
7. `probe_script_path()` points at an existing file. This guards the parent's path
   arithmetic only — it passes in any source checkout and says **nothing** about wheel
   packaging, so it does not close criterion 8.
8. **Real-child smoke test:** run `probe.py info json pytest nosuchmodule_xyz` under
   `sys.executable` and assert `importable == {"json": True, "pytest": True,
   "nosuchmodule_xyz": False}` and that `version` matches `platform.python_version()`.

Every test that touches the cache must call `get_environment_info.cache_clear()`. Put the
autouse fixture in **`tests/conftest.py`**, not in this module: the `lru_cache` is
process-wide, step 6 adds `tests/test_tool_context.py` as a second consumer, and an xdist
worker runs many modules per process, so a module-scoped fixture leaves the cache warm for
whatever runs next.

**Criterion 8 — `probe.py` in a built wheel** — needs a test that inspects a wheel.
`tests/test_packaging.py`, `@pytest.mark.integration`. `build` creates an isolated
environment and installs the build backend into it, so this is tens of seconds:

```
pytest.importorskip("build")
execute_command([sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
                cwd=<repo root>, timeout_seconds=300)
names = zipfile.ZipFile(next(tmp_path.glob("*.whl"))).namelist()
assert "mcp_tools_py/utils/target_scripts/probe.py" in names
assert "mcp_tools_py/utils/target_scripts/__init__.py" in names
```

This is the only form that distinguishes "present in the checkout" from "shipped", which
is exactly what the criterion asks and what a later reorganisation would break silently
(the third rejected alternative in the issue).

`build` is in neither `dependencies` nor the `dev` extra today, and CI installs `.[dev]`
(`ci.yml:131`), so `importorskip` would skip the test locally **and** in CI — criterion 8
would never actually be checked. **Add `"build>=1.0"` to the `dev` extra
(`pyproject.toml:46-51`) in this step.** Keep the `importorskip` as the guard for anyone
running without the extra, per the knowledge base's skip-don't-fake rule.

`tests/test_tool_availability/test_is_tool_available.py` (11 tests) currently patches
`mcp_tools_py.server.execute_command` and asserts a `python -m <tool> --version`
subprocess was run. Repoint the survivors at `mcp_tools_py.server.get_environment_info` (or
patch `execute_command` inside `environment_info`).

**Delete three tests** — they assert mechanics the probe removes, named in "#229 behaviours
that need no carry-over" above:

- `:43` `test_script_on_disk_skips_subprocess` and `:60`
  `test_script_group_fast_path_records_binary` — the fast path that let a script on disk
  answer for a *module* tool, and its `_tool_binaries` write, are both gone.
- `:159` `test_probe_disables_plugin_autoload` — `find_spec` executes nothing, so there is
  no autoload to disable.

**Two tests invert**, because the probe is shared: `:135`
`test_execution_error_without_timeout_caches_false` and `:219`
`test_subprocess_failure_marks_unavailable` both simulate a failing subprocess, which is now
a failing *probe* and therefore fails open. Rewrite them as "the probe succeeds and reports
`importable["pytest"] is False` → unavailable", which is the behaviour that actually
survives.

**Re-anchor, do not delete, `:101` `test_timeout_fails_open_and_caches`** onto the probe:
a timed-out probe still reports pytest available, still logs a warning, and is still cached
after one call. It is the test that pins the fail-open policy.

The rest keep their behaviour with the patch target changed: `:17` first call probes, `:82`
a console-script-only tool never probes, `:182` a second call runs no further subprocess,
`:200` an eagerly detected tool is answered from the cache, `:244` a successful probe marks
available.

**`execute_command` leaves `server.py` in this step**, so every
`patch("mcp_tools_py.server.execute_command")` in the suite raises `AttributeError` once
the now-dead import is removed. There are 24 sites across three files:

| File | Lines |
|---|---|
| `test_is_tool_available.py` | `:21,47,64,86,107,139,163,186,205,223,248` |
| `test_resolve_python_executable.py` | `:22,39,68,83,102,119` |
| `test_handler_short_circuit.py` | `:18,43,68,93,127,168,200` |

Those in `test_is_tool_available.py` belong to the tests handled above. The thirteen in the
other two files patch it only to keep server construction from spawning subprocesses, which
the lazy probe (decision 14) already guarantees. **Delete those thirteen `patch(...)`
context-manager entries and the `mock_exec.return_value = ...` lines that feed them**,
rather than repointing them; nothing in those tests asserts on the mock. Removing the import
and leaving any of them in place turns the file red, so both halves land in this commit.

## Checks

`run_format_code`, `run_pylint_check`, `run_pytest_check`, `run_mypy_check`,
`run_lint_imports_check` (the new contract must pass), `run_tach_check`
(`target_scripts` sits under `utils`, adds no dependency edge). `probe.py` lives in `src`
so ruff's `D`/`DOC` rules and mypy strict apply to it — annotate fully and docstring it.

The two new tests are `integration`-marked, so run them explicitly as well:
`run_pytest_check(extra_args=["-n","auto"], markers=["integration"])`.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_2.md`, then implement step 2.
> Write `tests/test_environment_info.py` first, then `probe.py` (stdlib imports only —
> `json`, `sys`, `platform`, `importlib.util`, `importlib.metadata`), then
> `environment_info.py` (moving `PROBE_TIMEOUT_SECONDS`, `TOOL_MODULES` and `TOOL_PACKAGES`
> there from `server.py` so the ten-tool taxonomy has one home), then rewire
> `server._is_tool_available` — keeping #229's fail-open policy, so a failed or timed-out
> probe reports the five module tools available with a warning, and keeping its
> console-script-only branch, which the probe cannot answer — drop the now-dead
> `execute_command` import from `server.py` and fix all 24
> `patch("mcp_tools_py.server.execute_command")` sites in `tests/test_tool_availability/`,
> deleting the three tests the step names. Add the `.importlinter`
> contract together with `tests/test_target_scripts_contract.py`, which proves it fails
> when `probe.py` imports a project module; do not verify that by hand. Add
> `tests/test_packaging.py` for the wheel, together with `"build>=1.0"` in
> `pyproject.toml`'s `dev` extra — without it that test skips everywhere and criterion 8
> goes unchecked. Put the `get_environment_info.cache_clear()` autouse fixture in
> `tests/conftest.py`. One commit, all checks passing, including the
> integration-marked run. Do not add a `source` subcommand yet — step 3 owns it.
