# Step 2 — black and isort resolve from the tool environment

Formatters only read source text, so by the rule stated in `utils/tool_context.py` they
belong in mcp-tools-py's own env, not the project env. mcp-tools-py already declares both
as its dependencies.

This step is **only** the env move. No new steps, no resolution logic — those come later.
Its failure mode is an availability regression, so it lands alone and is verified alone.

## WHERE

**Modify**
- `src/mcp_tools_py/utils/environment_info.py`
- `src/mcp_tools_py/formatter/black_runner.py`
- `src/mcp_tools_py/formatter/isort_runner.py`
- `src/mcp_tools_py/formatter/runner.py`
- `src/mcp_tools_py/formatter/formatter_tools.py`
- `tests/test_black_runner.py`
- `tests/test_isort_runner.py`
- `tests/test_formatter_tools.py`

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
) -> FormatterResult: ...


def run_isort(
    python_executable: str,          # deprecated: accepted and ignored
    ...
) -> FormatterResult: ...
```

Signatures are **unchanged**. `python_executable` stays first, is never read, and its
docstring says so. This is what keeps mcp_coder working: it calls
`run_black(sys.executable, ...)` directly at `src/mcp_coder/mcp_tools_py.py:57` today, and
the reroute (mcp_coder#1173) has **not** landed. Ignoring the argument closes that window
before and after.

Do not remove the parameter. Removing it is later cleanup, not this issue.

### 3. Resolving the binary — one shared helper

Add to `formatter/runner.py` (the runners import it from there, or from `common.py` once
step 3 creates it — either is fine, pick one and keep it):

```python
def formatter_binary(name: str) -> str | None:
    """Locate `name`'s console script in mcp-tools-py's own environment."""
```

Implementation is two lines: `PythonEnvironment.resolve().binary(name)`, returned as
`str` or `None`. `PythonEnvironment.resolve()` with no arguments is `sys.executable`'s
environment — exactly what `ToolContext.tool_environment` defaults to.

`formatter/runner.py` has no `ToolContext`, which is why it resolves this itself. That is
also what makes "ignore `python_executable`" truthful rather than cosmetic.

When the binary is absent, return the existing `execution_error`-shaped `FormatterResult`:
`output=f"{tool} is not available: no console script found in {bin_dir}"`,
`success=False`, `files_changed=[]`. The MCP layer checks availability upfront anyway;
this is the direct-caller path.

### 4. `formatter_tools.py`

No signature change. `is_tool_available("black")` / `("isort")` now answer from the
filesystem instead of the probe — no code edit needed, `CONSOLE_SCRIPT_TOOLS` membership
does it.

## ALGORITHM

```
binary = formatter_binary("black")            # tool env, not python_executable
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
silently passes for the wrong reason. Replace it with a patch of
`tool_context.tool_environment.binary` returning `None` for `"black"` — or delete the
black binary from the `tool_context` fixture's script directory, which the fixture
docstring already documents as the intended mechanism.

`tests/test_formatter_tools.py:59` (`test_default_steps_isort_then_black`) is **not**
affected by this step — the "neither declared → error" rule does not exist yet. It is
fixed in step 6.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports pass. Watch specifically for failures in
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
> (`PythonEnvironment.resolve().binary(name)`) instead of
> `[python_executable, "-m", tool]`.
>
> Keep `python_executable` as the first parameter of both runners. It is accepted and
> ignored — deprecated — and the docstring must say so. mcp_coder still calls these
> directly with `sys.executable`; removing the parameter would break it.
>
> Write the tests first, including one that passes a bogus `python_executable` and asserts
> the same binary still runs. Rewrite `test_tool_unavailable_returns_error` in
> `tests/test_formatter_tools.py` to patch `tool_environment.binary` rather than the
> probe — patching the probe is now a no-op and the test would pass for the wrong reason.
>
> Do not update any documentation counts; step 8 does that. Do not add ruff steps or
> resolution logic.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check` and
> `run_lint_imports_check`. All must pass. Then make exactly one commit.
