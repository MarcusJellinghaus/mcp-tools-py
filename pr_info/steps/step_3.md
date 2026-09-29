# Step 3 — `formatter/common.py`: shared output helpers and version reporting

`black_runner.py` and `isort_runner.py` each carry an identical 10-line
`_truncate_output` and an identical timed-out / execution-error /
combine-stdout-and-stderr preamble. Steps 4 and 5 add two more runners, which would make
four copies. This step extracts them once, and adds version reporting while the two
existing runners are open.

Result: the codebase is shorter after this issue than before it.

## WHERE

**Modify** `src/mcp_tools_py/formatter/common.py` — step 2 created it with
`formatter_binary`; this step adds the output helpers and version reporting alongside
**Create** `tests/test_formatter_common.py`
**Modify** `src/mcp_tools_py/formatter/black_runner.py`, `isort_runner.py`,
`tests/test_black_runner.py`, `tests/test_isort_runner.py`

## WHAT

```python
MAX_LINES = 200


def truncate_output(text: str) -> str:
    """Cap `text` at MAX_LINES, appending a marker when it was cut."""


def combine_output(result: CommandResult) -> str:
    """Join a command's stdout and stderr into one block."""


def formatter_version(distribution: str) -> str:
    """Version of `distribution` in mcp-tools-py's own environment.

    Returns the installed version, or "unknown" when it cannot be determined.
    """


def version_line(tool: str, distribution: str | None = None) -> str:
    """One-line version banner to prepend to a FormatterResult.output."""
```

`truncate_output` and `combine_output` are the existing bodies, moved verbatim. The
leading underscore is dropped — they are now package-internal shared helpers, not
module-private ones.

### Why `importlib.metadata`, not `--version`

All four formatters resolve from `tool_environment`, which is
`PythonEnvironment.resolve()` with no arguments — `sys.executable`'s environment, the
process mcp-tools-py runs in, and not configurable from the CLI. So
`importlib.metadata.version("black")` reports the exact distribution whose console script
is about to run.

This deviates from the issue text, which specifies one `--version` subprocess per step
inside that step's timeout budget. The acceptance criterion — *each step's `output` names
the formatter version it ran* — is met identically, with four fewer subprocesses, no
timeout interaction, and a one-line degradation path.

**Put a comment at `formatter_version` recording the coupling:** this is exact only while
`tool_environment` is not CLI-configurable. If that ever changes, swap the body for a
`--version` subprocess — one function, and the call sites do not move.

## ALGORITHM

```
formatter_version(dist):
    try:    return importlib.metadata.version(dist)
    except PackageNotFoundError: return "unknown"

version_line(tool, dist=None):
    return f"{tool} {formatter_version(dist or tool)}"
```

`distribution` defaults to `tool` and differs only where the names diverge. black, isort
and ruff all match, so the parameter exists for honesty, not for a current caller.

## DATA

`FormatterResult` gains **no field**. The version is prepended as a line to
`output`, deliberately — a second mcp_coder-visible API change is not worth it:

```
black 24.8.0
<the formatter's own output>
```

## HOW

In each runner, after the successful-command branch:

```python
output = f"{version_line('black')}\n{combine_output(result)}"
return FormatterResult(output=truncate_output(output), ...)
```

The version line goes **inside** the truncation input, so a 200-line cap still yields a
banner. The timed-out and execution-error early returns keep their current bare messages
— a version banner on "black timed out" is noise.

## TESTS

`tests/test_formatter_common.py` — **write first**:

1. `truncate_output` under the cap returns the input unchanged.
2. Over the cap: 200 lines plus a `... (truncated, N more lines)` marker.
3. `combine_output` joins both streams; each of stdout-only, stderr-only and neither.
4. `formatter_version("black")` returns something non-empty and not `"unknown"` — black
   is a declared dependency, so it is installed in the test environment.
5. `formatter_version("definitely-not-a-distribution")` returns `"unknown"`. Assert the
   degradation, not an exception.

`tests/test_black_runner.py` / `tests/test_isort_runner.py`:

6. A successful run's `output` first line names the tool and a version.
7. The timed-out and execution-error paths carry **no** version banner.

Existing truncation tests in the two runner test modules can point at the shared helper
or stay as-is; do not rewrite what already passes.

## DONE WHEN

pylint / pytest / mypy / tach / lint-imports pass. `common.py` must not import from
`runner.py` or `formatter_tools.py` — it sits below both.

---

## LLM PROMPT

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_3.md`.
>
> Extend `src/mcp_tools_py/formatter/common.py` — created in step 2 with
> `formatter_binary` — with `truncate_output` and
> `combine_output` — moved verbatim from the duplicated private copies in
> `black_runner.py` and `isort_runner.py` — plus `formatter_version(distribution)` and
> `version_line(tool, distribution=None)`.
>
> `formatter_version` uses `importlib.metadata.version` and returns `"unknown"` on
> `PackageNotFoundError`. This is exact because all four formatters now resolve from
> mcp-tools-py's own environment, which is the running process's environment. Add a
> comment recording that coupling and the `--version`-subprocess revert path.
>
> Wire both existing runners to the shared helpers and have each prepend a version line
> to `output`, inside the truncation input. The timed-out and execution-error early
> returns get no banner.
>
> Write the tests first, including the `"unknown"` degradation case.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check` and
> `run_lint_imports_check`. All must pass. Then make exactly one commit.
