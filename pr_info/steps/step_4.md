# Step 4 — jedi resolves against the configured environment

`jedi.Project` gains `environment_path`, so `list_symbols` and `find_references` stop
falling back to `VIRTUAL_ENV` / "the latest Python on the system". Ends with the
integration test that would have caught the reported bug.

**Acceptance criterion closed:** "With `--venv-path` pointing at a venv containing a
package absent from the tool env, `get_library_source` returns that package's source and
`list_symbols` resolves against it."

## WHERE

**Created**
- `tests/test_environment_integration.py`

**Modified**
- `src/mcp_tools_py/refactoring/jedi_tools.py`
- `src/mcp_tools_py/refactoring/__init__.py` — `RefactoringTools.__init__`
- `src/mcp_tools_py/server.py:87` — pass the environment
- `tests/test_refactoring/test_refactoring_tools.py` — constructor call sites
- `tests/test_refactoring/test_jedi_tools.py` — one new construction test

## WHAT

```python
# jedi_tools.py
@lru_cache(maxsize=None)
def _get_project(project_dir: str, interpreter: str | None) -> tuple[Any | None, str | None]: ...

def list_symbols(project_dir: Path, file_path: str, interpreter: str | None = None) -> str: ...
def find_references(project_dir: Path, file_path: str, symbol_name: str,
                    interpreter: str | None = None) -> str: ...

# refactoring/__init__.py
class RefactoringTools:
    def __init__(self, project_dir: Path, environment: PythonEnvironment,
                 timeout: int = 120) -> None: ...
```

`interpreter=None` means "jedi's default environment", exactly today's behaviour.
Production always passes the resolved interpreter. The default exists so the ~13 existing
jedi tests need no edit and the suite does not spawn thirteen `CompiledSubprocess`
children — `jedi.Project(environment_path=...)` creates a fresh `Environment` per project,
and `Environment.__init__` spawns eagerly.

Step 7 converts `RefactoringTools` to `ToolContext`; this step's constructor change is the
first of two small edits to the same call sites.

## ALGORITHM

```
_get_project(project_dir, interpreter):
    import jedi
    try:
        if interpreter is None:
            return jedi.Project(path=project_dir), None
        return jedi.Project(path=project_dir, environment_path=interpreter), None
    except Exception as exc:                      # jedi.InvalidPythonEnvironment and friends
        return None, (f"Error: cannot analyse against the Python environment at "
                      f"'{interpreter}': {exc}")

list_symbols / find_references:
    ... existing file-exists check ...
    project, error = _get_project(str(project_dir), interpreter)
    if error is not None: return error
    script = jedi.Script(code=source, path=str(abs_path), project=project)
    ... unchanged from here ...
```

Catching `Exception` matches the existing idiom in this file (`:29`, `:118`, both with
`# pylint: disable=broad-exception-caught`) and avoids importing jedi's private exception
path. The message names the interpreter, so an unusable environment surfaces as text
rather than a traceback.

`environment_path=`, not `sys_path=` (decision 2): a `sys.path` override avoids jedi's
child interpreter but still infers against the *tool* env's stdlib and builtins.
`load_unsafe_extensions` stays `False` (decision 11).

## DATA

`_get_project` returns `(project, None)` or `(None, error_message)`. Failures are cached
alongside successes, because `lru_cache` stores the returned tuple — a fixed environment
requires a server restart either way, and this avoids a spawn attempt per call
(decision 3). No lock: the MCP SDK calls sync tools directly without threadpool
offloading, so tool calls do not overlap (decision 4, `rope_tools.py:433`).

The cached project holds a live `CompiledSubprocess` for the server's lifetime. That is
the intended trade and is why the cache exists.

## Tests

**Unit** — `tests/test_refactoring/test_jedi_tools.py`, one new test:

Patch `jedi.Project` and assert it is called with `environment_path` set to the
interpreter passed in. This is the structural guard; the existing thirteen tests keep
calling without an interpreter and stay untouched.

**Integration** — `tests/test_environment_integration.py`, `@pytest.mark.integration`:

```
env_dir = tmp_path / "env"
venv.EnvBuilder(with_pip=False).create(env_dir)                     # ~1 s
site = sysconfig.get_paths(vars={"base": str(env_dir), "platbase": str(env_dir),
                                 "installed_base": str(env_dir)})["purelib"]
write <site>/probe_only_pkg/__init__.py containing `class Marker:` and a function
interpreter = PythonEnvironment.resolve(venv_path=str(env_dir)).interpreter
```

Assertions:

1. `_get_library_source("probe_only_pkg.Marker", 200, str(interpreter))` contains
   `class Marker` — **resolves through the target venv**.
2. The same call with `sys.executable` returns "not found" — **and not through the tool
   env**. Together these two are the only assertions in the suite that would have caught
   the reported bug.
3. `list_symbols(project_dir, file, interpreter=str(interpreter))` succeeds against the
   foreign venv — proving `InvalidPythonEnvironment` does not fire and the
   `CompiledSubprocess` starts.

Be explicit in the test's docstring about what assertion 3 does and does not prove: our
two jedi tools list and cross-reference names *within the project*, so no exposed jedi
call is environment-sensitive the way `get_library_source` is. The environment-sensitive
guarantee for jedi is the construction assertion in the unit test above; assertion 3 is
the real-venv smoke test.

Resolve `site-packages` with `sysconfig.get_paths(vars=...)` rather than hardcoding — the
layout differs by platform. Call `_get_project.cache_clear()` in teardown so the jedi
child is not left to be reaped at interpreter exit.

`venv.EnvBuilder(with_pip=False)` keeps this near 1 s; pip is not needed, since
`environment_path` and the `probe.py` child only need a real interpreter.

## Checks

`run_format_code`, `run_pylint_check`, `run_mypy_check`, then both pytest runs:

```
run_pytest_check(extra_args=["-n","auto","-m","not integration"])
run_pytest_check(extra_args=["-n","auto"], markers=["integration"])
```

The second is the one that matters here. Also `run_lint_imports_check` and
`run_tach_check` — `refactoring` already declares `mcp_tools_py.utils`.

## LLM prompt

> Read `pr_info/steps/summary.md` and `pr_info/steps/step_4.md`, then implement step 4.
> Write the `jedi.Project(environment_path=...)` construction test and
> `tests/test_environment_integration.py` first, then add `_get_project` to
> `jedi_tools.py`, thread `interpreter` through both public functions, and pass the
> environment from `server.py` through `RefactoringTools`. Do not edit the thirteen
> existing jedi tests — if one needs editing, the `interpreter=None` default is wrong.
> Run the integration-marked tests explicitly; they are skipped by the default filter.
> One commit, all checks passing.
