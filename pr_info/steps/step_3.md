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


def formatter_version(
    distribution: str,
    environment: PythonEnvironment | None = None,
) -> str:
    """Version of `distribution` in the environment the binary comes from.

    Returns the installed version, or "unknown" when it cannot be determined.
    """


def version_line(
    tool: str,
    distribution: str | None = None,
    environment: PythonEnvironment | None = None,
) -> str:
    """One-line version banner to prepend to a FormatterResult.output."""
```

`truncate_output` and `combine_output` are the existing bodies, moved verbatim. The
leading underscore is dropped — they are now package-internal shared helpers, not
module-private ones.

### Why `importlib.metadata`, not `--version`

The version must describe the binary that was actually invoked. Step 2 made the
environment a **caller-supplied, injectable** parameter — `formatter_binary(name,
environment)`, with the MCP layer passing `self.context.tool_environment` and
`tests/conftest.py:78` injecting a tmp script directory — so `formatter_version` takes the
**same** `environment` its caller passed to `formatter_binary`. Reading
`importlib.metadata.version()` unconditionally would report the running process's
distribution no matter which environment the binary came from, which is the divergence
step 2 exists to prevent.

When `environment` is `None`, or when its interpreter is the running one, the running
process **is** the environment the console script comes from, so
`importlib.metadata.version(distribution)` names the exact distribution. That is the
production path: `tool_environment` is `sys.executable`'s environment and is not
configurable from the CLI. Any other environment is answered from the existing cached
`get_environment_info(interpreter).distributions` probe in `utils/environment_info.py`,
keyed by lowercased distribution name — no new subprocess per step, because that probe is
one-shot and `lru_cache`d per interpreter.

This deviates from the issue text, which specifies one `--version` subprocess per step
inside that step's timeout budget. The acceptance criterion — *each step's `output` names
the formatter version it ran* — is met identically, with four fewer subprocesses, no
timeout interaction, and a one-line degradation path.

**Put a comment at `formatter_version` recording the revert path:** if the metadata route
ever stops matching the invoked binary, swap the body for a `--version` subprocess — one
function, and the call sites do not move.

## ALGORITHM

```
formatter_version(dist, environment=None):
    if environment is None or environment.interpreter == Path(sys.executable):
        try:    return importlib.metadata.version(dist)
        except PackageNotFoundError: return "unknown"
    info = get_environment_info(str(environment.interpreter))
    return info.distributions.get(dist.lower(), "unknown")   # "unknown" on probe error

version_line(tool, dist=None, environment=None):
    return f"{tool} {formatter_version(dist or tool, environment)}"
```

Each runner passes the `environment` it received, so the banner and the binary always come
from one place:

```python
output = f"{version_line('black', environment=environment)}\n{combine_output(result)}"
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
output = f"{version_line('black', environment=environment)}\n{combine_output(result)}"
return FormatterResult(output=truncate_output(output), ...)
```

`environment` is the runner's own keyword-only parameter from step 2 — the same value it
passed to `formatter_binary`, so the banner names the environment the binary came from.

The version line goes **inside** the truncation input, so a 200-line cap still yields a
banner. The timed-out and execution-error early returns keep their current bare messages
— a version banner on "black timed out" is noise.

### This changes `FormatterResult.output` for `black` and `isort`

The banner is a deliberate, user-visible change to the `output` **text** of the two
existing steps: `output` now begins with `black <version>` rather than with black's own
first line. `success`, `files_changed` and `unparsable_files` are untouched, and
`files_changed` is still parsed from the formatter's own output, not from the banner-prefixed
string.

The "existing explicit `["isort", "black"]` behaviour unchanged — regression criterion" at
`step_6.md:215` and `step_7.md:59` therefore means **which steps run, in which order, with
which results** — it does **not** cover `output` content. Any existing test asserting
`output` equality for black or isort is updated here, in this step, to expect the banner;
that is not a weakening of the regression criterion.

## TESTS

`tests/test_formatter_common.py` — **write first**:

1. `truncate_output` under the cap returns the input unchanged.
2. Over the cap: 200 lines plus a `... (truncated, N more lines)` marker.
3. `combine_output` joins both streams; each of stdout-only, stderr-only and neither.
4. `formatter_version("black")` returns something non-empty and not `"unknown"` — black
   is a declared dependency, so it is installed in the test environment.
5. `formatter_version("definitely-not-a-distribution")` returns `"unknown"`. Assert the
   degradation, not an exception.
5b. **The environment governs the answer.** `formatter_version("black", environment=env)`
   for an `env` whose interpreter is *not* `sys.executable` goes through the probe, not
   through `importlib.metadata`: patch `get_environment_info` to report a distinct
   `distributions` mapping and assert that version comes back. A probe error, or a
   distribution the probe does not list, degrades to `"unknown"`.
5c. An `environment` whose interpreter *is* `sys.executable` gives the same answer as
   `environment=None`.

`tests/test_black_runner.py` / `tests/test_isort_runner.py`:

6. A successful run's `output` first line names the tool and a version. With an injected
   `environment`, the banner reports **that** environment's version — the same environment
   the invoked binary came from, per step 2's threaded parameter.
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
> `black_runner.py` and `isort_runner.py` — plus
> `formatter_version(distribution, environment=None)` and
> `version_line(tool, distribution=None, environment=None)`.
>
> `formatter_version` takes the **same** `environment` its caller passed to
> `formatter_binary`, so the banner describes the binary that actually ran. When
> `environment` is `None` or names the running interpreter, use
> `importlib.metadata.version` and return `"unknown"` on `PackageNotFoundError`;
> otherwise read the version from the cached
> `get_environment_info(interpreter).distributions` probe, degrading to `"unknown"`. Do
> not read `importlib.metadata` unconditionally — the environment is injectable
> (`tests/conftest.py:78`), so that would report the running process's version for a
> binary that came from somewhere else. Add a comment recording the
> `--version`-subprocess revert path.
>
> Wire both existing runners to the shared helpers and have each prepend a version line
> to `output`, inside the truncation input, passing their own `environment` through. The
> timed-out and execution-error early returns get no banner.
>
> Write the tests first, including the `"unknown"` degradation case and the case where an
> injected environment governs the reported version.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check` and
> `run_lint_imports_check`. All must pass. Then make exactly one commit.
