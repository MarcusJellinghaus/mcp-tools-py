# Step 4 — `runners.py`: transport the exit code and pytest's `-m` error line

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_4.md`), and
> issue #294 (decisions 12, 18, 19, Constraints "The exit code is lost on the error
> path", "Hint text stays out of `verdict.problems`"). Steps 1–3 are done. Implement
> step 4 only: tests first, then code, run the checks listed in the summary, then
> commit (one commit).

## WHERE

- Modified: `src/mcp_tools_py/code_checker_pytest/runners.py`
- Modified: `tests/test_code_checker_pytest/test_runners.py`

## WHAT

```python
# Attributes run_tests sets on an exception it re-raises, next to _COMMAND_ATTR.
_EXIT_CODE_ATTR = "pytest_exit_code"
_MARKER_ERROR_ATTR = "pytest_marker_error"

MARKER_ERRORS = (
    "Unknown marker(s) in '-m' expression",
    "Wrong expression passed to '-m'",
)

def marker_error_line(stderr: str) -> str | None:
    """pytest's ERROR: line for a -m problem, from the full stderr, or None."""
```

`check_code_with_pytest` result gets two keys on **both** paths:

- `"exit_code"`: `int | None` — error path: the attribute (None for timeouts,
  execution errors, missing report with no exit code); success path:
  `verdict.exit_code`.
- `"marker_error"`: `str | None` — error path: the attribute; success path: `None`.

## HOW

- In `run_tests`, keep `exit_code: int | None = None` and
  `marker_error: str | None = None` before the inner `try`. Set `exit_code =
  process.returncode` right after `ProcessResult` is built; set `marker_error =
  marker_error_line(error_output)` when `process.returncode == 4`.
- In the existing inner `except Exception as e:` handler, next to
  `setattr(e, _COMMAND_ATTR, shown_command)`, set both new attributes.
- In `check_code_with_pytest`'s `except`, read them with `getattr(e, …, None)`.
- `RunVerdict(RunStatus.ERROR, problems, 0)` stays — no `Exit code N` line.
- `_build_error_detail` / `truncate_stderr` unchanged.

## ALGORITHM — `marker_error_line`

```
for line in stderr.splitlines():
    line = line.strip()
    if line.startswith("ERROR:") and any(m in line for m in MARKER_ERRORS):
        return line
return None
```

## DATA

pytest 9 text: `ERROR: Unknown marker(s) in '-m' expression: a, b. Use 'pytest --markers' to see available markers.`
and `ERROR: Wrong expression passed to '-m': <expr>: <reason>`.

## Tests (write first) — `test_runners.py`

Mock `execute_command` with `make_command_result` (from `tests/conftest.py`), as the
existing tests do.

- exit 4 with stderr = 600 chars of warnings + `ERROR: Unknown marker(s) in '-m' expression: unit. Use …`
  → `result["exit_code"] == 4`, `result["marker_error"]` is that line, and the
  verdict's problems are unchanged (still the 500-char cut).
- exit 4 with `ERROR: Wrong expression passed to '-m': …` → `marker_error` set.
- exit 4 with an unrelated usage error (`ERROR: unrecognized arguments: --bogus`)
  → `marker_error is None`, `exit_code == 4`.
- exit 5 → `exit_code == 5`, `marker_error is None`, problems still start with
  `No Tests Found`.
- exit 3 → `exit_code == 3`.
- timeout → `exit_code is None`.
- verdict on the error path still has `exit_code == 0`.
- success path → `result["exit_code"] == verdict.exit_code`, `marker_error is None`.
- `marker_error_line` unit cases: no ERROR line, ERROR line not about `-m`.
