# Step 7 — Failed collectors become findings

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_7.md`.
> Write the tests first, then the implementation. Run pylint, mypy and pytest
> (`extra_args=["-n", "auto", "-m", "not integration"]`), then run
> `tests/test_toolkit_saved_coverage.py` explicitly (its module is marked
> `integration`, so the fast run hides it). Format the code and make exactly
> one commit.

## WHERE

- `src/mcp_tools_py/toolkit.py` — new `_collector_findings`, `_XDIST_KEY`,
  `_run_test`
- `tests/test_toolkit_test.py`, `tests/test_toolkit_saved_coverage.py`

## WHAT

```python
_XDIST_KEY = "pytest|collection|xdist"

def _collector_findings(report: PytestReport) -> list[Finding]: ...
def _is_collection_error(report: PytestReport, verdict: RunVerdict) -> bool: ...
```

## HOW

- Imports: `XDIST_MARKER` from `code_checker_pytest.reporting`, `XDIST_HINT`
  from `code_checker_pytest.verdict`. Filter collectors with the existing
  `_FAILED_OUTCOMES`; no change to `reporting.py`.
- In `_run_test`, compute collector findings right after `finished` and
  **before** the `known` gate (a real collection failure arrives as ERROR, so
  acting after the gate is too late):

```python
collector_findings = _collector_findings(report) if report is not None else []
collection_error = report is not None and _is_collection_error(report, verdict)
if report is None or (
    verdict.status not in known and not (collection_error and collector_findings)
):
    ...  # unchanged skipped / error returns
findings = [<test findings as today>, *collector_findings]
```

- Only an ERROR caused by collection errors is bypassed. Every other ERROR
  (internal error, usage error, KeyboardInterrupt, timeout/kill) stays
  `error`, even when the report also holds a failed collector. New helper in
  `toolkit.py`:

```python
_COLLECTION_INTERRUPTED = "during collection"  # pytest: "Interrupted: N error(s) during collection"

def _is_collection_error(report: PytestReport, verdict: RunVerdict) -> bool:
    """True when an ERROR verdict was caused by collection errors."""
    if verdict.status is not RunStatus.ERROR:
        return False
    if verdict.exit_code == 1:  # TESTS_FAILED with no failed/errored test: collectors only
        return True
    output = report.error_context.error_message if report.error_context else ""
    return verdict.exit_code == 2 and _COLLECTION_INTERRUPTED in output
```

  Exit code 2 is also pytest's code for a KeyboardInterrupt, which is why
  exit 2 additionally needs pytest's "during collection" line. Codes 3
  (internal error), 4 (usage error) and 5 (no tests) never qualify. The
  real-run tests in this step (`test_every_module_failing_to_import_is_findings`
  and `test_failing_collector_under_xdist_saves_the_data`) confirm the
  exit-code/output shape. If either run ends with a different shape, stop
  and write it to `pr_info/.blocked.txt` instead of widening the rule.

- Locations for `fix_text` (from step 4): node id for tests and collectors,
  `None` for the xdist finding — e.g.
  `locations = [f.key if f.path else None for f in findings]` with a comment,
  or build the list alongside the findings.
- The rest is unchanged: `findings_summary` already uses `failed_summary`
  when `collectors_failed_line(report)` is non-empty; the
  `FAILED and not findings` branch still covers runs without collectors.
- Update `_run_test`'s docstring.

## ALGORITHM

```
by_id, xdist = {}, None
for c in report.collectors or [] with c.outcome in _FAILED_OUTCOMES:
    text = c.longrepr or ""
    if XDIST_MARKER in text: xdist = xdist or Finding(key=_XDIST_KEY, message=f"{XDIST_MARKER}\n{XDIST_HINT}")
    elif c.nodeid not in by_id:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        by_id[c.nodeid] = Finding(key=c.nodeid, message=lines[-1] if lines else "collection failed",
                                  path=c.nodeid.split("::")[0])
return [*by_id.values(), *([xdist] if xdist else [])]
```

## DATA

- Per collector: `Finding(key=nodeid, message=<last non-empty longrepr line or "collection failed">, path=<file>)`.
- xdist: one `Finding(key="pytest|collection|xdist", path=None)` carrying the hint once.
- Skipped/passed collectors produce nothing.

## Tests (write first)

`tests/test_toolkit_test.py`:

- `test_every_module_failing_to_import_is_error` → rename
  `test_every_module_failing_to_import_is_findings`, **remove** its
  `@pytest.mark.integration`; real run → status `"findings"`, finding keys end
  with `test_a.py` / `test_b.py`, messages contain
  `module_that_does_not_exist`.
- `test_failed_with_failing_test_and_collectors_shows_both`: keys ==
  `["tests/test_a.py::test_x", "tests/test_b.py", "tests/test_c.py"]`;
  summary assertions unchanged.
- `test_failed_without_failing_tests_is_error` → `…_is_findings`: status
  `"findings"`, one finding keyed `tests/test_broken.py`; summary still holds
  `summary_text` and the problem.
- `test_failed_without_failing_tests_counts_collectors`: status
  `"findings"`; count line still precedes the problem.
- `test_failed_without_collector_keeps_summary`: unchanged (`error`).
- New:
  - `make_pytest_results` hard-codes `exit_code=0`, so build these results'
    `verdict` as `RunVerdict(RunStatus.ERROR, [problem], <code>)` directly
    (or give the helper an optional `exit_code`), and give the report an
    `error_context` whose `error_message` holds the pytest output.
  - Collection-error ERROR + one failed collector → `"findings"`,
    parametrized: exit 2 with output
    `"Interrupted: 1 error during collection"`, and exit 1.
  - Unrelated ERROR + one failed collector stays `"error"`, parametrized:
    exit 3 (internal error), and exit 2 with `KeyboardInterrupt` output and no
    "during collection" line.
  - empty `longrepr` → message `"collection failed"`.
  - same node id twice → one finding.
  - a collector with outcome `"skipped"` / `"passed"` → no finding.
  - two xdist collectors (`gw0`, `gw1`, longrepr containing
    `"Different tests were collected"`) → exactly one finding keyed
    `pytest|collection|xdist`, `path is None`, `XDIST_HINT` appears once in
    `fix_text`.

`tests/test_toolkit_saved_coverage.py`:

- `test_failing_collector_under_xdist_saves_the_data`: status
  `"findings"`; docstring → "A failed collector under xdist is a finding, and
  the partial run's data is saved." `test_failed_without_findings_saves_the_data`
  stays `error` (no collectors).
