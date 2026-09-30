# Step 2 — black and isort resolve from the tool environment

Formatters only read source text, so by the rule stated in `utils/tool_context.py` they
belong in mcp-tools-py's own env, not the project env. mcp-tools-py already declares both
as its dependencies.

This step is **only** the env move. No new steps, no resolution logic — those come later.
Its failure mode is an availability regression, so it lands alone and is verified alone.

## WHERE

**Create**
- `src/mcp_tools_py/formatter/common.py` — `formatter_binary` only; step 3 extends it

**Modify**
- `src/mcp_tools_py/utils/environment_info.py`
- `src/mcp_tools_py/formatter/black_runner.py`
- `src/mcp_tools_py/formatter/isort_runner.py`
- `src/mcp_tools_py/formatter/runner.py`
- `src/mcp_tools_py/formatter/formatter_tools.py`
- `tests/test_black_runner.py`
- `tests/test_isort_runner.py`
- `tests/test_formatter_tools.py`
- `vulture_whitelist.py`

## WHAT

### 1. The env move itself — two dict values

`utils/environment_info.py`:

```python
TOOL_MODULES: dict[str, Optional[str]] = {
    "pytest": "pytest",
    "pylint": "pylint",
    "mypy": "mypy",
    "black": None,     # was "black"
    "isort": None,     # was "isort"
    ...
}
```

`CONSOLE_SCRIPT_TOOLS`, `PROBED_MODULES` and `TOOL_DISTRIBUTIONS` are all derived from
`TOOL_MODULES` and follow automatically, as do `tests/conftest.py`,
`tests/test_tool_context.py` and `tests/test_server_params.py`, which parametrize over
`CONSOLE_SCRIPT_TOOLS`. **Change nothing in them beyond what actually fails.**

### 2. The runners build a console-script command

```python
def run_black(
    python_executable: str,          # deprecated: accepted and ignored
    target_dirs: list[str],
    project_dir: str,
    check_only: bool = False,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
    *,
    environment: PythonEnvironment | None = None,
) -> FormatterResult: ...


def run_isort(
    python_executable: str,          # deprecated: accepted and ignored
    ...
    *,
    environment: PythonEnvironment | None = None,
) -> FormatterResult: ...
```

The existing parameters are **unchanged** in order and meaning; `environment` is added
last and keyword-only, so every existing positional call still binds as before.
`python_executable` stays first, is never read, and its docstring says so. This is what keeps mcp_coder working: it calls
`run_black(sys.executable, ...)` directly at `src/mcp_coder/mcp_tools_py.py:57` today, and
the reroute (mcp_coder#1173) has **not** landed. Ignoring the argument closes that window
before and after.

Do not remove the parameter. Removing it is later cleanup, not this issue.

**Keeping vulture clean.** `run_black` and `run_isort` never read `python_executable`, so
vulture reports it as an unused variable at 100% confidence — above CI's
`--min-confidence 60`. `runner.py::run_format_code` still forwards it positionally to the
runners, so it is used there and not reported. Add one bare-name entry to
`vulture_whitelist.py`, next to the other bare names:

```python
python_executable  # Deprecated runner parameter, accepted and ignored until mcp_coder#1173
```

A bare name covers every function with that parameter, so `run_ruff_format` and
`run_ruff_imports` (steps 4 and 5) need no further entry.

### 3. Resolving the binary — one shared helper

**Create `src/mcp_tools_py/formatter/common.py` in this step** and put the helper there.
It must **not** go in `formatter/runner.py`: `runner.py` imports `run_black` and
`run_isort` from the two runner modules, so having those modules import back from
`runner.py` is a circular import that fails at import time. Step 3 extends the same
`common.py` with the output helpers; this step creates it with `formatter_binary` alone.

```python
def formatter_binary(name: str, environment: PythonEnvironment | None = None) -> str | None:
    """Locate `name`'s console script, defaulting to mcp-tools-py's own environment."""
```

**The environment is passed in by the caller.** `ToolContext.tool_environment` is an
injectable field — `tests/conftest.py:78` constructs a `ToolContext` over a tmp script
directory — so a runner that read a module-level accessor instead would invoke a
different binary from the one `is_tool_available("black")` was answered against. Thread
the environment through instead:

- `run_black` / `run_isort` gain a trailing keyword-only
  `environment: PythonEnvironment | None = None`.
- `runner.py::run_format_code` gains the same trailing keyword-only parameter and passes
  it to each runner. Adding it last and keyword-only keeps mcp_coder's existing
  positional `run_black(sys.executable, ...)` call working. **Its own
  `python_executable` docstring is marked deprecated too** — accepted and ignored, exactly
  as on `run_black` / `run_isort`; the issue names all three functions.
- `formatter_tools.py` passes `environment=self.context.tool_environment`, so the MCP
  layer's availability check and the invoked binary are the *same* environment object.

`None` means "mcp-tools-py's own environment", which is what a direct runner caller such
as mcp_coder gets. `formatter_binary` answers it with `PythonEnvironment.resolve()` — the
same call `ToolContext.tool_environment`'s existing `default_factory` makes, so an
un-injected context and a direct runner caller agree by construction. **No new accessor
and no cache:** `resolve()` reads `sys.executable` on every call, and
`tests/test_tool_availability/_helpers.py::_patched_tool_env` fakes a tool env by patching
`sys.executable`, while `server.py:54` builds `ToolContext` without `tool_environment`. A
cached default would pin the real env per xdist worker and break
`tests/test_server_params.py:795` / `:819` depending on test order. `default_factory` and
`_patched_tool_env`'s docstring stay as they are.

Layering stays downward: `formatter` → `utils`.

`formatter/runner.py` has no `ToolContext`, which is why the environment arrives as a
plain `PythonEnvironment` argument rather than as a context object. That is also what
makes "ignore `python_executable`" truthful rather than cosmetic: the selecting argument
is `environment`, not the interpreter path.

When the binary is absent, return the existing `execution_error`-shaped `FormatterResult`:
`output=f"{tool} is not available: no console script found in {bin_dir}"`,
`success=False`, `files_changed=[]`. The MCP layer checks availability upfront anyway;
this is the direct-caller path.

### 4. `formatter_tools.py`

No MCP signature change. `is_tool_available("black")` / `("isort")` now answer from the
filesystem instead of the probe — `CONSOLE_SCRIPT_TOOLS` membership does that with no
edit. The one edit here is passing `environment=self.context.tool_environment` to
`_run_format_code`, so the environment the availability check consulted is the one the
runners invoke.

## ALGORITHM

```
binary = formatter_binary("black", environment)   # caller's env, not python_executable
if binary is None: return unavailable FormatterResult
command = [binary] + (["--check"] if check_only else []) + target_dirs
result  = execute_command(command, cwd=project_dir, timeout_seconds=...)
... existing timed_out / execution_error / parse handling, unchanged ...
```

The only change to each runner is the first two lines of command construction. Everything
downstream — truncation, changed-file parsing, isort's unparsable-file handling — stays
byte-identical.

## DATA

`FormatterResult` unchanged.

## TESTS

**Write these first.**

`tests/test_black_runner.py` / `tests/test_isort_runner.py`:

1. The command's argv[0] is the tool-env console script and `"-m"` does **not** appear.
   Patch `formatter_binary` to return a known path.
2. **Passing a bogus `python_executable` does not change which binary runs** — call with
   `"/nonexistent/python"` and assert the same argv. This is an acceptance criterion.
3. Missing binary → `success=False` and a message naming the tool, with no subprocess run.
4. Existing parse / truncation / timeout tests unchanged — they are the regression that
   the move touched nothing else.

`tests/test_formatter_tools.py:288` (`test_tool_unavailable_returns_error`) **must be
rewritten**. It currently patches the probe via `make_environment_info(black=False)`.
Once black is a console-script tool, `is_tool_available("black")` is answered from the
filesystem and never consults the probe, so that patch becomes a no-op and the test
silently passes for the wrong reason. Rewrite it to **delete the black stub from the
`tool_context` fixture's script directory** — the mechanism the fixture docstring
documents, and the one `tests/test_checker_tools.py:21` already uses:

```python
binary = tool_context.tool_environment.binary("black")
assert binary is not None
binary.unlink()
```

Do not patch `tool_environment.binary` on the instance: `PythonEnvironment` is
`@dataclass(frozen=True)`, so `patch.object` on it raises `FrozenInstanceError`.

5. **The injected environment governs the binary.** Call `run_black` with an
   `environment` pointing at a tmp script directory and assert argv[0] is that
   directory's script, not the one `PythonEnvironment.resolve()` would return. This is what the
   threaded parameter buys: without it the `tool_context` fixture at
   `tests/conftest.py:78` would advertise one environment and the runner would invoke
   another.

`tests/test_formatter_tools.py:59` (`test_default_steps_isort_then_black`) is **not**
affected by this step — the "neither declared → error" rule does not exist yet. It is
fixed in step 6.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports / ruff / vulture pass. Watch specifically for failures in
`test_tool_context.py` and `test_server_params.py`: those parametrize over
`CONSOLE_SCRIPT_TOOLS` and are the signal that the derived sets moved correctly.

Docstring and README counts are **deliberately left stale** until step 8, which sweeps
them in one commit.

---

## LLM PROMPT

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_2.md`.
>
> Set `"black": None` and `"isort": None` in `TOOL_MODULES` in
> `src/mcp_tools_py/utils/environment_info.py`, and change `black_runner.py` and
> `isort_runner.py` to invoke the console script from mcp-tools-py's own environment
> instead of `[python_executable, "-m", tool]`.
>
> Put the `formatter_binary` helper in a **new** `src/mcp_tools_py/formatter/common.py` —
> not in `runner.py`, which already imports both runner modules and would make the import
> circular. Step 3 extends the same file.
>
> `formatter_binary(name, environment=None)` takes the environment from its caller. Add a
> trailing keyword-only `environment: PythonEnvironment | None = None` to `run_black`,
> `run_isort` and `runner.py::run_format_code`, and have the MCP layer pass
> `environment=self.context.tool_environment` — `ToolContext.tool_environment` is
> injectable (`tests/conftest.py:78` supplies a tmp script directory), so reading a
> module-level accessor inside the runner would invoke a different binary from the one
> `is_tool_available` was answered against. `None` falls back to
> `PythonEnvironment.resolve()`, uncached — do not add an accessor or a cache; existing
> tests fake the tool env by patching `sys.executable`.
>
> Keep `python_executable` as the first parameter of both runners. It is accepted and
> ignored — deprecated — and the docstring must say so. Mark `runner.py::run_format_code`'s
> own `python_executable` docstring deprecated the same way. mcp_coder still calls these
> directly with `sys.executable`; removing the parameter would break it.
>
> Write the tests first, including one that passes a bogus `python_executable` and asserts
> the same binary still runs. Rewrite `test_tool_unavailable_returns_error` in
> `tests/test_formatter_tools.py` to delete the black stub from the `tool_context`
> fixture's script directory (`tool_context.tool_environment.binary("black").unlink()`)
> rather than patching the probe — patching the probe is now a no-op and the test would
> pass for the wrong reason. Do not patch `binary` on the instance: `PythonEnvironment` is
> a frozen dataclass.
>
> Add `python_executable` as a bare name to `vulture_whitelist.py` — the runners never
> read it, and vulture reports that at 100% confidence.
>
> Do not update any documentation counts; step 8 does that. Do not add ruff steps or
> resolution logic.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check`,
> `run_lint_imports_check`, `run_ruff_check` and `run_vulture_check`. All must pass. Then
> make exactly one commit.
