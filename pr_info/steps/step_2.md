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
- `src/mcp_tools_py/server.py` — `_is_tool_available`; the `execute_command` import goes
  with it (this was its last use, so ruff/pylint flag it otherwise)
- `tests/test_tool_availability.py` — `TestIsToolAvailable` (`:244-347`), **and** the ten
  `patch("mcp_tools_py.server.execute_command")` sites outside it

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
7. `probe_script_path()` points at an existing file. This guards the parent's path
   arithmetic only — it passes in any source checkout and says **nothing** about wheel
   packaging, so it does not close criterion 8.
8. **Real-child smoke test:** run `probe.py info json pytest nosuchmodule_xyz` under
   `sys.executable` and assert `importable == {"json": True, "pytest": True,
   "nosuchmodule_xyz": False}` and that `version` matches `platform.python_version()`.

Every test that touches the cache must call `get_environment_info.cache_clear()` — put it
in an autouse fixture in this module.

**Criterion 8 — `probe.py` in a built wheel** — needs a test that inspects a wheel.
`tests/test_packaging.py`, `@pytest.mark.integration` (it builds a distribution, so it is
seconds, not milliseconds):

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
(the third rejected alternative in the issue). Skip rather than fake when `build` is
absent, per the knowledge base.

`tests/test_tool_availability.py` — `TestIsToolAvailable` (`:244-347`) currently patches
`mcp_tools_py.server.execute_command` and asserts a subprocess was run. Repoint it at
`mcp_tools_py.server.get_environment_info` (or patch `execute_command` inside
`environment_info`) and keep the same four behaviours: first call probes, second call is
cached, an eager console-script tool never probes, a failed probe marks unavailable.

**`execute_command` leaves `server.py` in this step**, so every
`patch("mcp_tools_py.server.execute_command")` in the suite raises `AttributeError` once
the now-dead import is removed. Fifteen sites exist; five are inside `TestIsToolAvailable`
and are handled above. The other ten are at `:34`, `:51`, `:80`, `:96`, `:378`, `:403`,
`:428`, `:453`, `:487` and `:527` — they patch it only to keep server construction from
spawning subprocesses, which the lazy probe (decision 14) already guarantees. **Delete
those ten `patch(...)` context-manager entries and the `mock_exec.return_value = ...`
lines that feed them**, rather than repointing them; nothing in those tests asserts on the
mock. Removing the import and leaving any of the ten in place turns the file red, so both
halves land in this commit.

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
> `environment_info.py`, then rewire `server._is_tool_available`, drop the now-dead
> `execute_command` import from `server.py` and fix all fifteen
> `patch("mcp_tools_py.server.execute_command")` sites in
> `tests/test_tool_availability.py` — five repointed, ten deleted. Add the `.importlinter`
> contract together with `tests/test_target_scripts_contract.py`, which proves it fails
> when `probe.py` imports a project module; do not verify that by hand. Add
> `tests/test_packaging.py` for the wheel. One commit, all checks passing, including the
> integration-marked run. Do not add a `source` subcommand yet — step 3 owns it.
