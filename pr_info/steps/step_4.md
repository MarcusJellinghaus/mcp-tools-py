# Step 4 — jedi resolves against the configured environment

`jedi.Project` gains `environment_path`, so `list_symbols` and `find_references` stop
falling back to `VIRTUAL_ENV` / "the latest Python on the system". Ends with the
integration test that would have caught the reported bug.

**Acceptance criterion closed:** "With `--python-executable` pointing into a venv containing
a package absent from the tool env, `get_library_source` returns that package's source and
`list_symbols` resolves against it." Stated through `--python-executable`, not
`--venv-path`: #229 deprecated the latter, and the criterion is about the resolution target,
not the flag that supplies it.

## WHERE

**Created**
- `tests/test_environment_integration.py`

**Modified**
- `src/mcp_tools_py/refactoring/jedi_tools.py`
- `src/mcp_tools_py/refactoring/__init__.py` — `RefactoringTools.__init__`
- `src/mcp_tools_py/server.py:112` — pass the environment
- `tests/test_refactoring/test_refactoring_tools.py` — constructor call sites, plus the two
  direct `jedi_tools` call sites at `:71` and `:86`
- `tests/test_refactoring/test_jedi_tools.py` — ten call sites gain the interpreter, plus
  one new construction test
- `tests/test_refactoring/test_integration.py:78,84,138` — three call sites
- `tests/test_refactoring/test_lazy_imports.py:62` — the `list_symbols(...)` snippet run in
  the child interpreter

## WHAT

```python
# jedi_tools.py
@lru_cache(maxsize=None)
def _get_project(project_dir: str, interpreter: str) -> tuple[Any | None, str | None]: ...

def list_symbols(project_dir: Path, file_path: str, interpreter: str) -> str: ...
def find_references(project_dir: Path, file_path: str, symbol_name: str,
                    interpreter: str) -> str: ...

# refactoring/__init__.py
class RefactoringTools:
    def __init__(self, project_dir: Path, environment: PythonEnvironment,
                 timeout: int = 120) -> None: ...
```

`interpreter` is **required**, matching step 3's rule for `_get_library_source`. A `None`
default meaning "jedi's default environment" would keep the
pre-fix resolution path — `VIRTUAL_ENV`, then conda, then "the latest Python on the
system" — reachable from any call site that forgets the argument, which is exactly the
defect this issue exists to remove. The same decision must not come out two different ways
for the two tools.

The cost is that the fifteen existing call sites listed above must be edited, and that each
distinct `(project_dir, interpreter)` now spawns one `CompiledSubprocess`:
`Project.get_environment()` creates a fresh `Environment` per project and
`Environment.__init__` spawns eagerly. Pass `sys.executable` in those tests — the same
interpreter running the suite, so inference results are unchanged — and see the teardown
note under Tests. `test_lazy_imports.py:62` targets a **missing** file, which returns
before `_get_project` is reached, so that test spawns nothing and keeps proving the lazy
import.

Step 7 converts `RefactoringTools` to `ToolContext`; this step's constructor change is the
first of two small edits to the same call sites.

## ALGORITHM

```
_get_project(project_dir, interpreter):
    import jedi
    try:
        project = jedi.Project(path=project_dir, environment_path=interpreter)
        project.get_environment()                 # force it HERE - see below
        return project, None
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

**`jedi.Project(...)` alone raises nothing.** `Project.__init__` only stores
`environment_path`; the environment is built lazily in `Project.get_environment()`, which
calls `create_environment(...)` — and *that* is what raises `InvalidPythonEnvironment` and
spawns the `CompiledSubprocess`. Its first caller is `jedi.Script(...)`, at
`jedi_tools.py:27` and `:99`, which sits **outside** every `try` in that file. A `try`
wrapped around the constructor alone would therefore catch nothing: the traceback would
still escape from the `Script` line, and the `lru_cache` would have stored a "successful"
project whose environment fails on every call.

Calling `project.get_environment()` inside the `try` is what makes the promise below
true. `Project.get_environment()` memoises on the project (`if self._environment is None`),
so forcing it here is not an extra spawn — it moves the one spawn inside the guarded,
cached region, and the later `jedi.Script(...)` reuses the already-built environment and
cannot raise `InvalidPythonEnvironment`.

Catching `Exception` matches the existing idiom in this file (`:29`, `:118`, both with
`# pylint: disable=broad-exception-caught`) and avoids importing jedi's private exception
path. The message names the interpreter, so an unusable environment surfaces as text
rather than a traceback.

Test this directly: patch `jedi.Project` so that `get_environment()` raises, call
`list_symbols`, and assert the returned string names the interpreter — no exception
propagates — and that a second call does not re-attempt (the failure is cached).

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
interpreter passed in. This is the structural guard.

A second new test covers the failure path, which is where the constructor-only `try` would
have leaked: make the patched project's `get_environment()` raise, then assert
`list_symbols` **returns** a string naming the interpreter rather than propagating, and
that a second call does not re-attempt (`_get_project` cached the failure).

**Existing call sites** — the fifteen listed under WHERE all gain the interpreter. Add a
module-level helper in `test_jedi_tools.py` so the edit is mechanical and the choice is
visible, mirroring step 3's `_src`:

```python
def _symbols(project_dir: Path, file_path: str) -> str:
    return list_symbols(project_dir, file_path, sys.executable)
```

Every call now builds a `jedi.Environment`, so add an autouse teardown fixture calling
`_get_project.cache_clear()` in `test_jedi_tools.py`, `test_integration.py` and
`test_refactoring_tools.py`. Dropping the cached projects releases the `CompiledSubprocess`
children instead of leaving them to be reaped at interpreter exit — the same reason the
integration test below clears the cache.

**Integration** — `tests/test_environment_integration.py`, `@pytest.mark.integration`:

```
env_dir = tmp_path / "env"
venv.EnvBuilder(with_pip=False).create(env_dir)                     # ~1 s
paths = sysconfig.get_paths(vars={"base": str(env_dir), "platbase": str(env_dir),
                                  "installed_base": str(env_dir)})
write <paths["purelib"]>/probe_only_pkg/__init__.py containing `class Marker:` and a function
python = Path(paths["scripts"]) / ("python.exe" if os.name == "nt" else "python")
interpreter = PythonEnvironment.resolve(python_executable=str(python)).interpreter
```

Resolve through `python_executable`, not the deprecated `venv_path`: the criterion is about
the resolution target, and `sysconfig` already yields the `scripts` directory here, so the
test needs no `Scripts`/`bin` branch of its own.

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
> `jedi_tools.py`, thread a **required** `interpreter` through both public functions, and
> pass the environment from `server.py` through `RefactoringTools`. Do not give
> `interpreter` a `None` default — that would keep the `VIRTUAL_ENV` fallback this issue
> removes. Update the fifteen existing call sites listed in the step to pass
> `sys.executable`, and add the `_get_project.cache_clear()` teardown fixtures.
> Run the integration-marked tests explicitly; they are skipped by the default filter.
> One commit, all checks passing.
