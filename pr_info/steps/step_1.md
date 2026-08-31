# Step 1 — Detect unparsable files, fail the step, report them

Read [summary.md](./summary.md) first for context, scope, and the design
rationale.

Single commit: tests + implementation + passing checks.

---

## LLM Prompt

> Implement Step 1 of the plan in `pr_info/steps/`. Read `summary.md` for
> context and design rationale, then this file (`step_1.md`) for the details.
>
> Fix issue #221: `run_format_code(check_only=True)` reports success when isort
> silently skips files it cannot encode. Parse isort's
> `Unable to parse file <path> due to <reason>` warnings, set
> `success = False` when any are present, and render an explicit warning block
> in the tool output.
>
> Follow TDD: write the two tests first, watch them fail, then implement. Touch
> only the five files listed under WHERE. Do not modify `runner.py`,
> `black_runner.py`, or the architecture docs — see "Out of scope" in
> `summary.md`.
>
> Read the Constraints section below before writing the test fixture; two of the
> constraints are non-obvious and one of them is self-referential.
>
> Verify with `run_pylint_check`, `run_pytest_check(extra_args=["-n", "auto"])`,
> `run_mypy_check` and `run_ruff_check`. Run `run_format_code` before
> committing, then update `pr_info/TASK_TRACKER.md`.

---

## WHERE

| File | Change |
|---|---|
| `tests/test_isort_runner.py` | Add fixture constant + one test |
| `tests/test_formatter_tools.py` | Extend `_make_formatter_result`; add one test |
| `src/mcp_tools_py/formatter/models.py` | Add field; update docstring |
| `src/mcp_tools_py/formatter/isort_runner.py` | Add parser; widen `success`; update docstring |
| `src/mcp_tools_py/formatter/formatter_tools.py` | Add `_unparsable_block`; render it |

No new files, folders or modules.

---

## WHAT

New symbols:

```python
# src/mcp_tools_py/formatter/isort_runner.py
_UNPARSABLE_RE: re.Pattern[str]
def _parse_isort_unparsable_files(output: str) -> list[str]: ...

# src/mcp_tools_py/formatter/formatter_tools.py
_UNPARSABLE_CAP: int = 10
def _unparsable_block(step: str, files: list[str]) -> str: ...
```

Changed signatures:

```python
# tests/test_formatter_tools.py
def _make_formatter_result(
    output: str = "output",
    success: bool = True,
    unparsable_files: list[str] | None = None,
) -> FormatterResult: ...
```

No production signature changes anywhere.

---

## HOW

**`models.py`** — the module uses `import dataclasses` / `@dataclasses.dataclass`
and never imports `field`, so a bare `field(...)` is a `NameError`. Use the
qualified form. The new field goes **last**; it is the only defaulted field, so
there is no ordering conflict.

```python
    output: str
    success: bool
    files_changed: list[str]
    unparsable_files: list[str] = dataclasses.field(default_factory=list)
```

Update the `Attributes:` block (`models.py:10-14`), including the now-false
`success: True when return_code == 0.` line:

```
        success: True when the formatter exited 0 and processed every target
            file.
        unparsable_files: Paths the formatter reported it could not read. A
            non-empty list means the run was incomplete.
```

**`isort_runner.py`** — add `import re` at the top. Place `_UNPARSABLE_RE`
beside `_MAX_LINES`, and `_parse_isort_unparsable_files` after
`_parse_isort_changed_files`. In `run_isort`, call it on the **untruncated**
`output` local, mirroring `files_changed=_parse_isort_changed_files(output)` at
line 81:

```python
    unparsable_files = _parse_isort_unparsable_files(output)

    return FormatterResult(
        output=_truncate_output(output),
        success=result.return_code == 0 and not unparsable_files,
        files_changed=_parse_isort_changed_files(output),
        unparsable_files=unparsable_files,
    )
```

Update the `Returns:` block at `isort_runner.py:61-62` to mention unparsable
files and the widened `success`.

**`formatter_tools.py`** — add `_unparsable_block` as a module-level function
next to `_format_results`, and call it inside the existing loop
(`formatter_tools.py:108-112`). Emit it **below** the `## <step>` header and
above the raw output: below the header preserves the existing assertion
`result.startswith("## isort")` at `tests/test_formatter_tools.py:306`.

```python
    for step in steps:
        if step in results:
            body = results[step].output
            if results[step].unparsable_files:
                block = _unparsable_block(step, results[step].unparsable_files)
                body = f"{block}\n{body}"
            sections.append(f"## {step}\n{body}")
            if not results[step].success:
                failed_step = step
```

Emit generically for any step, interpolating the step name. No
`step == "isort"` special case — it would be a dead branch for black.

**Docstrings** — `src/` is under ruff `D` + `DOC` (google convention, preview)
per `pyproject.toml:85-100`. Both new functions need a Google-style docstring
with a `Returns:` section. `tests/` is exempt at line 96.

---

## ALGORITHM

Parsing:

```
_UNPARSABLE_RE = re.compile(r"Unable to parse file (.+) due to ")
_parse_isort_unparsable_files(output):
    return _UNPARSABLE_RE.findall(output)
```

That single line satisfies every constraint by construction: it matches the
substring anywhere in the line (the real warning is prefixed
`<frozen runpy>:88: UserWarning: `, so `startswith` matches nothing); it never
splits on whitespace (Windows paths may contain spaces); greedy `(.+)` takes the
last `" due to "`; and `.` excludes newlines, so non-matching lines are skipped
and a wrapped message yields nothing rather than a glued-together path. All four
behaviours were verified against a hand-written `find`/`rfind` loop and found
identical.

Under mypy strict, `findall` is typed `list[Any]`; returning it from a
`-> list[str]` function does **not** trip `warn_return_any`, which fires only on
bare `Any`. Verified.

Block rendering:

```
_unparsable_block(step, files):
    lines = ["ERROR: {step} could not read {len(files)} file(s) - they were NOT checked.",
             "A clean result here does NOT mean CI will pass.",
             "Known limitation (Windows, piped stdout)."]
    lines += ["  " + path for path in files[:_UNPARSABLE_CAP]]
    if len(files) > _UNPARSABLE_CAP:
        lines.append("  ... and {len(files) - _UNPARSABLE_CAP} more")
    return "\n".join(lines)
```

---

## DATA

`FormatterResult.unparsable_files` — `list[str]`, defaults to `[]`, ordered as
isort emitted the warnings. Paths are verbatim from isort: on Windows,
backslash-separated and possibly containing spaces.

`_unparsable_block` returns a `str` with no trailing newline (the caller joins
it to the raw output). Rendered result for 11 files:

```
## isort
ERROR: isort could not read 11 file(s) - they were NOT checked.
A clean result here does NOT mean CI will pass.
Known limitation (Windows, piped stdout).
  src\mcp_tools_py\code_checker_pytest\reporting.py
  ... 9 more paths ...
  ... and 1 more
<isort's own output follows>
```

The full list stays visible below the block as isort's own warnings — that is
why the cap is safe.

---

## TESTS

Write these first. Both use mocked `execute_command` / direct calls, matching the
existing style — no real isort. See "Verification" in `summary.md` for why there
is no integration test.

**`tests/test_isort_runner.py`** — one test, covering both parsing and the
widened `success`; they are the same scenario with the same mock.

Fixture: a module-level constant holding a **verbatim** warning, prefix
included. It must contain (a) two warning lines, (b) a path containing a space,
(c) the indented `warn(...)` source line that `warnings.warn` prints after each
warning, to prove non-matching lines are ignored.

```python
_UNPARSABLE_OUTPUT = (
    "<frozen runpy>:88: UserWarning: Unable to parse file "
    "src\\mcp_tools_py\\code_checker_pytest\\reporting.py due to "
    "'charmap' codec can't encode character in position 23: "
    "character maps to <undefined>\n"
    '  warn(f"Unable to parse file {file}")\n'
    "<frozen runpy>:88: UserWarning: Unable to parse file "
    "tests\\my dir\\test_black_runner.py due to "
    "'charmap' codec can't encode character in position 4: "
    "character maps to <undefined>\n"
)
```

Assert, from `run_isort(..., check_only=True)` with `return_code=0` and that
string as stderr:

- `result.unparsable_files` equals the two paths, the spaced one intact and the
  `warn(...)` line absent;
- `result.success is False`, despite `return_code == 0`.

The existing tests already assert `success is True` for warning-free runs, so
the no-regression case is covered.

**`tests/test_formatter_tools.py`** — extend `_make_formatter_result` with
`unparsable_files: list[str] | None = None`, passing `list(unparsable_files or [])`
(a dataclass default alone is not enough to write the test). Import
`_format_results` alongside `FormatterTools`.

One test calling `_format_results` directly with a single `isort` result
carrying **11** unparsable paths — 11 exercises rendering, the cap, and the
remainder in one case. Assert:

- output still starts with `## isort`;
- the `ERROR: isort could not read 11 file(s)` line is present;
- the first and tenth paths appear, the eleventh does not;
- `... and 1 more` is present;
- the block precedes the raw output (compare `.index(...)` positions).

---

## CONSTRAINTS

- **The test fixture must contain no live trigger character.**
  `tests/test_isort_runner.py` has none today. Embedding a real `→` or `✅` would
  make that file the 12th masked file — invisible to the very check it tests.
  (`tests/test_black_runner.py:25,118` already contains `✨ 🍰`, which is why it
  is one of the 11.) Describe the character in prose; never paste one.
- **Pin the fixture to the single-line warning form.** A genuinely wrapped
  message would not match, by design — the parser must not glue lines together.
- **Match anywhere in the line, not at its start.** Both existing parsers in
  `isort_runner.py` (lines 39 and 41) use `startswith` and would match nothing
  here.
- **Parse before truncating.** `_MAX_LINES = 200` would otherwise drop warnings
  on a large repository. The existing call order already does this.
- **Build the block in `_format_results`, not in the runner's `output`.** On a
  124-file repository a summary appended to the runner's output is pushed off
  the end by the very warnings it summarises.
- **Do not re-litigate environment workarounds.** `PYTHONIOENCODING=utf-8`,
  `PYTHONUTF8=1`, `--quiet`, `--diff` and `--verbose` were all measured against
  the fault and none of them changes it.

---

## DONE WHEN

- Both new tests pass; all existing formatter tests still pass.
- `run_pylint_check`, `run_pytest_check(extra_args=["-n", "auto"])`,
  `run_mypy_check` and `run_ruff_check` are clean.
- `run_format_code` has been run, and no `.scratch/` directory remains.
- `pr_info/TASK_TRACKER.md` marks this step complete.
- One commit.
