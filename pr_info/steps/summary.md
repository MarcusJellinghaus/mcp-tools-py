# Summary — Issue #221: isort silently skips files in check mode

## Problem

`run_format_code(check_only=True)` reports a clean result when isort has silently
failed to check part of the repository.

On Windows with piped stdout, isort cannot encode non-cp1252 characters (`→`,
`✅`, `≤`, `✨`, box-drawing, emoji) while checking a file. It misfiles the
resulting `UnicodeEncodeError` as a parse failure, emits

```
<frozen runpy>:88: UserWarning: Unable to parse file <path> due to <reason>
```

on stderr, skips the file entirely — and **exits 0**. Eleven files in this
repository are affected today; 124 on `mcp_coder`, where the fault was first
found.

Because `run_isort` derives `success` from the exit code alone, the tool renders
a compromised run identically to a passing one. A probe file with deliberately
unsorted imports and an arrow in its docstring produced `rc=0`, no
`Imports are incorrectly sorted` line, and a clean report. The masking is total,
not partial.

CI runs isort on Linux, where the `charmap` codec is never selected and every
file is parsed. The local check structurally cannot see what CI checks, while
producing output identical to a passing run — false confidence, which is worse
than none.

## Scope

The fault is **check mode only**. Apply mode processes these files correctly
(measured: apply mode sorted a file containing `→`), and prints no warnings
because it never hits the error.

The underlying bug is isort's (9.0.1, shipped as a compiled mypyc wheel). It is
not fixable here, and there is no environment or flag workaround —
`PYTHONIOENCODING=utf-8` is already set for every subprocess by
`get_python_isolation_env()` and does not help. What is in scope is that
`run_format_code` currently gives no indication anything went wrong.

**In scope:** report the incomplete run truthfully.

**Out of scope:** black (exits 123 on unparsable files — already loud); the
upstream isort bug; a guard against trigger characters in this repo's own
sources; the stale formatter documentation in
`docs/architecture/architecture.md` and `README.md`.

## Solution

Detect the warnings, mark the step unsuccessful, and say so in the output.

1. `FormatterResult` gains a defaulted `unparsable_files: list[str]` field.
2. `isort_runner` parses the warnings out of the combined stdout/stderr and sets
   `success = return_code == 0 and not unparsable_files`.
3. `_format_results` renders an explicit warning block for any step reporting
   unparsable files.

## Architectural and design changes

**No structural change.** No new module, no new package, no signature change, no
import-contract impact. The `formatter` package keeps its existing shape:
`formatter_tools` (MCP registration and rendering) → `runner` (orchestration) →
`isort_runner` / `black_runner` (subprocess) → `models` (data).

The design changes are three, all local:

**`success` semantics widen from "exited 0" to "exited 0 and processed every
target file."** This is the load-bearing change. Leaving `success = True` on a
skipped-file run would reproduce this very bug inside the data model, where
future programmatic consumers inherit it. `.success` has exactly two production
readers — `runner.py:63` (fail-fast) and `formatter_tools.py:111` (failed-step
tracking) — and both behave correctly under the wider definition.

**`FormatterResult` gains a structured field rather than the runner embedding
prose in `output`.** The runner's `output` is capped at `_MAX_LINES = 200`; on a
124-file repository a summary appended there is pushed off the end by the very
warnings it summarises. Keeping the paths structured also means the verdict is
available to callers, not only to the rendered text. Parsing runs on the
untruncated `output` local, before `_truncate_output` — it already does for
`files_changed`.

**The warning block is emitted generically per step, with the step name
interpolated.** `_format_results` loops uniformly over steps; a
`step == "isort"` special case would be a dead branch for black. Consequently
the parsing is deliberately **not** mode-gated: an apply-mode run that ever did
warn would set `success = False` and halt before black via `runner.py:63`. That
is intended behaviour, not a regression.

`runner.py:63` fail-fast is **not** modified. It cannot trigger in check mode,
and if it ever triggered in apply mode, halting before black and printing
"Formatting stopped due to errors in isort step" is correct.

`FormatterResult` is public API — exported at `formatter/__init__.py:5` and
listed in `__all__`. Appending a defaulted field is backward-compatible: all
four constructors pass keyword arguments, nothing serializes, copies or compares
whole instances (no `dataclasses.asdict`/`replace`/`astuple`, no
`json.dumps`, every test assertion is per-field), so the changed `__eq__` is
inert.

## Files created or modified

No folders or modules are created.

| File | Change |
|---|---|
| `src/mcp_tools_py/formatter/models.py` | Modified — add `unparsable_files` field; update `Attributes:` block and the now-false `success` docstring |
| `src/mcp_tools_py/formatter/isort_runner.py` | Modified — add `_parse_isort_unparsable_files`; widen `success`; update `Returns:` block |
| `src/mcp_tools_py/formatter/formatter_tools.py` | Modified — add `_unparsable_block`; render it in `_format_results` |
| `tests/test_isort_runner.py` | Modified — one new test (parsing + `success is False` despite exit 0) |
| `tests/test_formatter_tools.py` | Modified — `unparsable_files` parameter on `_make_formatter_result`; one new rendering test |
| `pr_info/TASK_TRACKER.md` | Modified — populate the task list |

Untouched by design: `runner.py`, `black_runner.py`, `formatter/__init__.py`,
`server.py`, `.importlinter`, `tach.toml`.

## Step breakdown

**One step, one commit.** The change is ~25 lines of production code across
three files with no signature changes, no new module, and no import-contract
impact.

It is not splittable into independently committable parts. Landing the parser
and `success` change without the rendering leaves isort reporting
`success = False` with no explanatory text — strictly worse than either
endpoint. Landing the dataclass field alone is a commit containing a field
nothing sets. Both intermediate states are worse than the whole.

- [step_1.md](./step_1.md) — detect unparsable files, fail the step, report them

## Verification

`run_pylint_check`, `run_pytest_check(extra_args=["-n", "auto"])`,
`run_mypy_check`, `run_ruff_check`, then `run_format_code` before committing.

No real-isort integration test: the fault reproduces only on Windows with piped
stdout, so such a test would pass vacuously on the Linux CI runners — its own
instance of this bug.

## Follow-up outside this change

The originating CI incident on `mcp_coder` was attributed to *apply* mode
leaving files unsorted. Apply mode works correctly here, so that attribution
cannot be right as stated — most likely a check-mode verification step in that
flow. Re-verify on `mcp_coder` before closing #221. This is investigation on a
sibling repository, not part of this diff.
