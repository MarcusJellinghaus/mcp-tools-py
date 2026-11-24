# Step 6 — Failure blocks: one stage loop; passing output gains logs

## LLM prompt
Read `pr_info/steps/summary.md` (design changes 5 and 6) and this file; issue #293 D12, D23, D26 and the
"xdist longrepr header" constraint define the behaviour. Implement test-first. Run pylint, mypy and the
non-integration pytest suite. One commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/reporting.py`
- `src/mcp_tools_py/code_checker_pytest/utils.py` (`SHOW_OUTPUT_NOTE` wording)
- `src/mcp_tools_py/checker_tools/__init__.py` (caller: `include_print_output=True` → drop the argument)
- Tests: `tests/test_code_checker_pytest/test_reporting.py`, `test_failure_budget.py` (line 133:
  `include_print_output=False` → `capture=frozenset()`)

## WHAT
```python
ALL_CAPTURE = frozenset({"stdout", "stderr", "log"})

def capture_kinds(show_capture: str | None) -> frozenset[str]:
    """pytest's --show-capture value → kinds: None/'all' → ALL_CAPTURE, 'no' → empty, else {value}."""

class Sections:            # renamed from _Sections (used by report_extras in step 7)
    def named(self, label: str, text: str) -> None:
        """Add text if it fits, else record `label` as dropped."""

def create_prompt_for_failed_tests(report, capture: frozenset[str] = ALL_CAPTURE, max_failures=..., max_lines=..., max_chars=...)
```
- `_render_test(test, capture, max_lines, max_chars)` loops over the stages via a new
  `_render_stage(out, name, stage, capture)`; `_render_setup` is removed.
- `create_prompt_for_passing_output` adds a `"<Stage> log"` block per stage with records.
- `NO_CAPTURED_OUTPUT_NOTE = "Note: no passing test produced captured output or log records."`
- `SHOW_OUTPUT_NOTE` ends "...which shows the output and log records of passing tests."

## ALGORITHM
```
_render_test: header line; for name, stage in (Setup, Call, Teardown): if stage: _render_stage(...)
_render_stage(out, name, stage, capture):
    prefix = "" if name == "Call" else f"Test {name} "
    if name != "Call" and stage.outcome == "failed": add f"  {prefix}Outcome: failed" and crash lines (old _render_setup text)
    if name == "Call" and stage.crash: bounded "  Error Message: ..."
    longrepr = strip_xdist_header(stage.longrepr)
    if stage.outcome != "passed" and longrepr: fenced(f"{prefix}Longrepr", longrepr) elif traceback: traceback rows
    for kind in ("stderr", "stdout", "log") if kind in capture: fenced(f"{prefix}{Kind}", text)   # log via format_log_record
```
Labels stay as today (`Longrepr`, `Stdout`, `Test Setup Longrepr`, …); teardown uses `Test Teardown …`.

## DATA
Unchanged return types. A passed stage whose `longrepr` is only `[gw0] …` renders no `Longrepr` section.

## Tests (write first)
- Teardown failure (call passed, teardown failed, outcome `error`) shows `Test Teardown Longrepr`.
- Passed call stage with header-only longrepr → no `Longrepr:` section; failed stage with header → header removed.
- Log records shown as `Log` in the call block; setup/teardown records under their prefix.
- `capture=frozenset()` hides stdout, stderr and logs; `{"log"}` shows only logs; `{"stdout"}` only stdout.
- `capture_kinds` for `no`, `stdout`, `stderr`, `log`, `all`, `None`.
- Passing output includes log records; existing budget tests stay green.
