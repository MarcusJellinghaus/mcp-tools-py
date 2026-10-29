# Step 1: `verdict.py`: classifier and shared text helpers

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_1.md`. Write the tests in `tests/test_code_checker_pytest/test_verdict.py` first, then `src/mcp_tools_py/code_checker_pytest/verdict.py`, then the package exports. Do not touch `runners.py`, the formatter, `toolkit.py` or `pytest_tool.py` in this step. Run pylint, mypy, pytest (`-n auto`), lint-imports and tach, and make sure all of them pass. Run `run_format_code`, then make one commit.

## Precondition

`reporting.py` must export `OutputBuilder`, `MAX_OUTPUT_LINES`, `FAILED_OUTCOMES` and `get_test_summary`, and `utils.py` must export `get_pytest_exit_code_info`. If any of them is missing, write one line to `pr_info/.blocked.txt` and stop.

## WHERE

- New: `src/mcp_tools_py/code_checker_pytest/verdict.py`
- New: `tests/test_code_checker_pytest/test_verdict.py`
- Modified: `src/mcp_tools_py/code_checker_pytest/__init__.py`. Import `RunStatus`, `RunVerdict` and `classify_run`, and add them to `__all__`.

## HOW

Imports in `verdict.py`, and nothing else from the project:

```python
from mcp_tools_py.code_checker_pytest.models import PytestReport, Summary
from mcp_tools_py.code_checker_pytest.reporting import (
    FAILED_OUTCOMES, MAX_OUTPUT_LINES, OutputBuilder, get_test_summary,
)
from mcp_tools_py.code_checker_pytest.utils import get_pytest_exit_code_info
```

`verdict.py` must not import `checker_tools` or `toolkit`.

## WHAT

```python
class RunStatus(str, Enum):
    PASSED = "passed"; FAILED = "failed"; ERROR = "error"; SUSPICIOUS = "suspicious"

@dataclass(frozen=True)
class RunVerdict:
    status: RunStatus
    problems: list[str]
    exit_code: int

XDIST_MARKER = "Different tests were collected"
XDIST_HINT: str   # cause plus workaround, see below
_ERROR_TAIL_LINES = 50

def classify_run(report: PytestReport) -> RunVerdict
def format_error_text(report: PytestReport | None, verdict: RunVerdict) -> str
def format_suspicious_text(collected: int) -> str
def format_collection_problems(report: PytestReport | None, verdict: RunVerdict) -> str

def _merge_problems(report: PytestReport, with_tail: bool) -> list[str]
def _dedup_key(text: str) -> str
def _cap_lines(problems: list[str]) -> str
def _xdist_hint(problems: list[str]) -> str
def _has_outcomes(summary: Summary) -> bool
def _has_collection_problems(report: PytestReport) -> bool
```

`XDIST_HINT` reads: "Hint: pytest-xdist workers collected different tests. Parametrize values must be identical across workers (no `datetime.now()` or random values). Pass `-n 0` to disable xdist and run the tests anyway."

## ALGORITHM

```text
classify_run(report):
  s, ctx = report.summary, report.error_context
  exit_code = ctx.exit_code if ctx else 0
  if (s.failed or 0) > 0 or (s.error or 0) > 0: status = FAILED
  elif exit_code != 0: status = ERROR
  elif s.collected > 0 and not _has_outcomes(s): status = SUSPICIOUS
  else: status = PASSED
  return RunVerdict(status, _merge_problems(report, with_tail=status is ERROR), exit_code)

_merge_problems(report, with_tail):
  items = [c.longrepr for c in report.collectors or [] if c.outcome in FAILED_OUTCOMES and c.longrepr]
  if ctx and ctx.collection_errors: items.append("\n".join(ctx.collection_errors))
  # ErrorContext holds the full output on every non-zero exit, so the tail is only used for ERROR
  if with_tail and not items and ctx and ctx.error_message.strip(): items.append(last _ERROR_TAIL_LINES lines of it)
  keep the first item for each _dedup_key(item)

_dedup_key(text):
  XDIST_MARKER if XDIST_MARKER in text else first line of text.strip()

format_error_text(report, verdict):
  lines = ["Pytest run reported an error."]
  lines += [get_test_summary(report)] if report and _has_outcomes(report.summary) else ["Pytest run did not complete."]
  if verdict.exit_code != 0 and not (verdict.exit_code == 2 and report and _has_collection_problems(report)):
      lines += [f"Exit code {code}: {get_pytest_exit_code_info(code)[0]}"]
  if verdict.problems: lines += ["Problems:", _cap_lines(verdict.problems) + _xdist_hint(verdict.problems)]
  return "\n".join(lines)

format_collection_problems(report, verdict):
  if not verdict.problems: return ""          # never reads report, so MagicMock reports are safe
  # Only what the failure prompt does not print: collection_errors and the xdist hint
  ctx = report.error_context if report else None
  body = _cap_lines(["\n".join(ctx.collection_errors)]) if ctx and ctx.collection_errors else ""
  hint = _xdist_hint(verdict.problems)
  return f"Collection problems:\n{body}{hint}".rstrip() if body or hint else ""
```

- `_cap_lines` creates an `OutputBuilder(MAX_OUTPUT_LINES)`, calls `add(p + "\n")` for each problem until `add` returns False, and returns `get_result()`.
- `_xdist_hint` returns `"\n" + XDIST_HINT` when any problem contains `XDIST_MARKER`, and `""` otherwise.
- `_has_outcomes` is True when any of passed, failed, error, skipped, xfailed or xpassed is greater than 0.
- `_has_collection_problems` is True when the report has failed collectors or `error_context.collection_errors`.
- `format_suspicious_text(n)` returns `f"Collected {n} tests but none reported an outcome. Not verified."`.

## DATA

- `classify_run` returns a `RunVerdict`. `problems` is always a list, possibly empty.
- Every `format_*` function returns a `str`. `format_collection_problems` returns `""` when there is nothing extra to show.

## Tests (`test_verdict.py`, written first)

Build `PytestReport` objects by hand, using a small local `_report(summary=..., collectors=..., error_context=...)` builder.

1. A table-driven `classify_run` test, one parametrized case per row:
   - Failures with exit 1 give `FAILED`.
   - Errors with exit 1 give `FAILED`.
   - Exit 1, `passed > 0`, no failures and no failed collectors gives `ERROR`.
   - Exit 2, a failed collector and zero outcomes gives `ERROR`.
   - Exit 0, `collected > 0` and every outcome None or 0 gives `SUSPICIOUS`.
   - Exit 0 with only skipped tests gives `PASSED`.
   - Exit 0 with only xfailed tests gives `PASSED`.
   - Exit 0 with passing tests gives `PASSED`.
   - No `ErrorContext` gives `exit_code == 0`.
2. Problem merging:
   - Collector `longrepr` comes before `collection_errors`.
   - The `error_message` tail is used only for `ERROR` and only when both are empty, and is capped at 50 lines.
   - A `FAILED` run (exit 1, `error_context` with only `error_message`) has empty `problems`.
3. De-duplication:
   - Three collectors whose texts differ but all contain "Different tests were collected …" yield one problem.
   - Two problems with the same first line yield one problem.
4. `format_error_text`:
   - Problems totalling more than `MAX_OUTPUT_LINES` lines produce the `Output truncated` marker, and the xdist hint still appears after it.
   - Exit 2 with a failed collector has no "interrupted by the user" text.
   - Exit 1 includes the exit-code line.
   - `format_error_text(None, RunVerdict(ERROR, ["Usage Error: x"], 0))` contains "did not complete" and "Usage Error: x", and has no "Exit code" line.
   - A report with outcomes includes the `get_test_summary` counts.
5. `format_collection_problems`:
   - It includes `collection_errors` and excludes everything else (collector `longrepr`, the `error_message` tail).
   - It returns `""` for empty problems.
   - It includes the xdist hint even when the xdist text came only from a collector.
6. `format_suspicious_text(3)` contains "Collected 3 tests" and "Not verified".
7. `RunStatus`, `RunVerdict` and `classify_run` can be imported from `mcp_tools_py.code_checker_pytest`.
