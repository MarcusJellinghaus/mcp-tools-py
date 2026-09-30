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


def formatter_version(binary: str, timeout_seconds: int) -> str:
    """Version reported by `binary --version`, or "unknown" when it cannot be determined."""


def version_line(tool: str, binary: str, timeout_seconds: int) -> str:
    """One-line version banner to prepend to a FormatterResult.output."""
```

`truncate_output` and `combine_output` are the existing bodies, moved verbatim. The
leading underscore is dropped — they are now package-internal shared helpers, not
module-private ones.

### Version from `<binary> --version`, as the issue specifies

The version must describe the binary that was actually invoked, so `formatter_version`
runs `[binary, "--version"]` on the **same path** `formatter_binary(name, environment)`
returned to the runner. That makes the injected environment govern the banner for free —
no metadata lookup, no environment parameter.

**It never fails the step.** A timed-out run, an `execution_error`, a non-zero exit, or
output with no recognisable version number all return `"unknown"`.

**Timeout budget.** The version call runs inside the step's own budget: after the step's
last formatter invocation, with whatever that invocation's `timeout_seconds` left unused.
Under one second left → skip the call and report `"unknown"`. A step's worst-case wall
time is therefore unchanged, and the timeout docs in step 8 need no version term.

**Probe the output first.** Before writing the parser, run `black --version`,
`isort --version` and `ruff --version` from the tool env via a `.scratch/` probe and record
the real stdout. Expected shapes differ — black prints `black, <v> (compiled: …)` plus a
Python line, ruff prints `ruff <v>`, isort prints an ASCII banner with `VERSION <v>` — so
the parser takes the **first** dotted version number (`\d+(\.\d+)+`) in stdout. Confirm
that the first match is the formatter's own version for all three, not a Python version.
Delete `.scratch/` when done.

## ALGORITHM

```
formatter_version(binary, timeout_seconds):
    if timeout_seconds < 1: return "unknown"
    result = execute_command([binary, "--version"], timeout_seconds=timeout_seconds)
    if result.timed_out or result.execution_error or result.return_code != 0:
        return "unknown"
    match = first r"\d+(\.\d+)+" in result.stdout
    return match or "unknown"

version_line(tool, binary, timeout_seconds):
    return f"{tool} {formatter_version(binary, timeout_seconds)}"
```

Each runner records `started = time.monotonic()` before its final formatter invocation and
passes the remainder, so the banner and the binary always come from one place:

```python
remaining = int(timeout_seconds - (time.monotonic() - started))
output = f"{version_line('black', binary, remaining)}\n{combine_output(result)}"
```

`formatter_version` calls `execute_command` through `common.py`'s **own** import, never
through the runner module's. The existing runner tests read `mock_exec.call_args` — the
**last** call — for argv and `timeout_seconds` (`tests/test_black_runner.py:40,51,161,170`,
`tests/test_isort_runner.py:55,66,191,200`), so a version call routed through the runner's
patched `execute_command` would replace the call they inspect.

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
remaining = int(timeout_seconds - (time.monotonic() - started))
output = f"{version_line('black', binary, remaining)}\n{combine_output(result)}"
return FormatterResult(output=truncate_output(output), ...)
```

`binary` is the path `formatter_binary("black", environment)` returned in step 2's code —
the one just invoked — so the banner names the binary that ran.

The version line goes **inside** the truncation input, so a 200-line cap still yields a
banner. The timed-out and execution-error early returns keep their current bare messages
and **run no version subprocess** — a version banner on "black timed out" is noise.

### This changes `FormatterResult.output` for `black` and `isort`

The banner is a deliberate, user-visible change to the `output` **text** of the two
existing steps: `output` now begins with `black <version>` rather than with black's own
first line. `success`, `files_changed` and `unparsable_files` are untouched, and
`files_changed` is still parsed from the formatter's own output, not from the banner-prefixed
string.

The "existing explicit `["isort", "black"]` behaviour unchanged — regression criterion" at
`step_6.md` (test 7) and `step_7.md` (test 4) therefore means **which steps run, in which order, with
which results** — it does **not** cover `output` content. Any existing test asserting
`output` equality for black or isort is updated here, in this step, to expect the banner;
that is not a weakening of the regression criterion.

## TESTS

`tests/test_formatter_common.py` — **write first**:

1. `truncate_output` under the cap returns the input unchanged.
2. Over the cap: 200 lines plus a `... (truncated, N more lines)` marker.
3. `combine_output` joins both streams; each of stdout-only, stderr-only and neither.
4. **Unmocked:** `formatter_version(<tool-env black binary>, 30)` returns a dotted version,
   not `"unknown"` — black is a declared dependency, so its console script exists.
5. Parsing, against mocked `common.execute_command` fed the **recorded** real stdout of
   `black --version`, `isort --version` and `ruff --version`: each yields the formatter's
   own version, never the Python version.
5b. **Degradation, never an exception:** timed out, `execution_error`, non-zero exit, and
   stdout with no version number each return `"unknown"`.
5c. The subprocess argv is `[binary, "--version"]` with the given `timeout_seconds`, and
   `timeout_seconds < 1` returns `"unknown"` without running anything.

`tests/test_black_runner.py` / `tests/test_isort_runner.py`:

Add an autouse fixture patching `<runner module>.version_line` to a fixed
`"<tool> 0.0.0"`, so no existing test spawns a version subprocess against its patched
binary path. Tests 6 and 7 assert on that mock's calls; the real subprocess is covered by
tests 4-5c above.

6. A successful run's `output` first line is the banner, and `version_line` received the
   **same binary path** the formatter command used (argv[0]) and a timeout no larger than
   the step's `timeout_seconds`.
7. The timed-out and execution-error paths carry **no** version banner and call
   `version_line` zero times.

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
> `formatter_version(binary, timeout_seconds)` and
> `version_line(tool, binary, timeout_seconds)`.
>
> `formatter_version` runs `[binary, "--version"]` — the **same** path the runner got from
> `formatter_binary` and just invoked — through `common.py`'s own `execute_command`
> import, and returns the first dotted version number in stdout. Timeout, execution
> error, non-zero exit or no match → `"unknown"`; it never fails the step. **Probe the real
> `--version` output of black, isort and ruff in `.scratch/` first** and write the parser
> against it; delete `.scratch/` when done.
>
> Wire both existing runners to the shared helpers and have each prepend a version line
> to `output`, inside the truncation input. The version call gets what is left of the
> step's `timeout_seconds` after the formatter invocation (measured with
> `time.monotonic()`); under one second left means `"unknown"`. The timed-out and
> execution-error early returns get no banner and run no version subprocess.
>
> Write the tests first, including the `"unknown"` degradation cases, parsing of recorded
> real output, and an autouse fixture in the runner test modules that patches
> `version_line` so existing `mock_exec.call_args` assertions still see the formatter
> call.
>
> Run `run_format_code`, `run_pylint_check`, `run_pytest_check` with
> `extra_args=["-n", "auto"]`, `run_mypy_check`, `run_tach_check` and
> `run_lint_imports_check`. All must pass. Then make exactly one commit.
