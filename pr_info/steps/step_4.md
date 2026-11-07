# Step 4 — Locations in `fix_text`

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_4.md`.
> Write the tests first, then the implementation. Run pylint, mypy and pytest
> (`extra_args=["-n", "auto", "-m", "not integration"]`), format the code, and
> make exactly one commit.

## WHERE

- `src/mcp_tools_py/toolkit_checks.py` — `_finding_line`,
  `_result_from_findings`, `_run_mypy`, `_run_pylint`, `_run_ruff`,
  `_run_bandit`, `_run_deptry`
- `src/mcp_tools_py/toolkit.py` — `_run_test`
- `tests/test_toolkit.py`, `tests/test_toolkit_check.py`,
  `tests/test_toolkit_check_mypy.py`, `tests/test_toolkit_test.py`

## WHAT

```python
def _finding_line(finding: Finding, location: str | None = None) -> str: ...

def _result_from_findings(
    error: str | None,
    findings: list[Finding],
    ok_summary: str,
    findings_summary: str,
    locations: list[str | None] | None = None,
) -> ActionResult: ...
```

Both new arguments are optional; omitted → output identical to today, so
`_run_format`, `_merge`'s fallback and `TestMerge` stay unchanged. Do not
touch `_merge`. `Finding` is not changed.

## HOW

Each runner builds `locations` where its message (with the line) is still
available:

| Runner | location |
|---|---|
| `_run_pylint` | `f"{message.path}:{message.line}"` |
| `_run_ruff` | `f"{message.filename}:{message.line}"` |
| `_run_bandit` | `f"{message.filename}:{message.line_number}"` |
| `_run_deptry` | `f"{message.file}:{message.line}"` if `message.line is not None` else `None` |
| `_run_mypy` | `f"{message.file}:{message.line}"` if `message.line >= 0` else `None`; used in its own `fix_text` loop: `_finding_line(finding, location)` followed by the hint lines |
| `_run_test` | `test.nodeid` for each failing test |

## ALGORITHM

```
_finding_line:
    where = location or finding.path
    prefix = ": ".join(p for p in (where, finding.rule) if p)
    return f"- {prefix}: {message}" if prefix else f"- {message}"
_result_from_findings (findings branch):
    locs = locations or [None] * len(findings)
    fix_text = "\n".join(_finding_line(f, loc) for f, loc in zip(findings, locs))
```

## DATA

- Check tools: `- src/a.py:12: E1101: message`
- mypy: `- src/mod.py:3: return-value: Bad return type` + indented hint lines
- test: `- tests/test_a.py::test_x: assert 1 == 2`

## Tests (write first)

- `tests/test_toolkit.py`: `_finding_line` with a location replaces the path;
  `_result_from_findings(..., locations=[...])` puts them in `fix_text`;
  existing `TestResultFromFindings` / `TestMerge` stay green unchanged.
- `tests/test_toolkit_check.py`: in the existing ruff, bandit and deptry
  finding tests (and a pylint one, following the file's patching pattern),
  assert `path:line` appears in `fix_text`; deptry with `line=None` shows the
  bare path.
- `tests/test_toolkit_check_mypy.py`: update `TestHints` expectations to
  `- src/mod.py:3: return-value: Bad return type` (hints unchanged below it);
  add a case with `line=-1` → no line number.
- `tests/test_toolkit_test.py`: `test_standard_failing_project_is_findings`
  asserts `"test_fail.py::test_fails"` is in `fix_text`.
