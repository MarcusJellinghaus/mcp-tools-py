# Step 5: Toolkit mypy mapping (notes, hints, signals)

**Commit message:** `fix(toolkit): report mypy hints and signals, exclude notes`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, `pr_info/steps/step_5.md`. Steps 1 to 4 are already committed. Implement this step only, tests first. Run the checks listed in the summary, fix what they report, then make exactly one commit.

## WHERE

- `src/mcp_tools_py/code_checker_mypy/reporting.py`: extract `format_hint_lines`
- `src/mcp_tools_py/toolkit_checks.py`: `_run_mypy`, new `_one_line`
- `tests/test_toolkit_check_mypy.py` (**new**)

## WHAT

```python
# reporting.py: _format_message uses it too
def format_hint_lines(hint: str | None) -> list[str]: ...

# toolkit_checks.py
def _one_line(text: str) -> str: ...
```

## HOW

- Add imports to `toolkit_checks.py`:
  - `from dataclasses import replace`
  - `from mcp_tools_py.code_checker_mypy.reporting import format_hint_lines, run_signals`
  - `MYPY_EXIT_PREFIX` from the existing `runners` import
- `_result_from_findings` stays unchanged, because other checkers share it.
- Leave `Finding.message` and `Finding.key` as they are. Do not dedupe hints: only the first import of a package carries the shared lines.
- Update the `_run_mypy` docstring: one Finding per non-note message.

## ALGORITHM

```python
issues = [m for m in result.messages if m.severity != "note"]
findings = [Finding(...same fields as today...) for m in issues]
fix_text = "\n".join(
    line for m, f in zip(issues, findings)
    for line in [_finding_line(f), *format_hint_lines(m.hint)]
)
suffix = "".join(f" {_one_line(signal)}" for signal in run_signals(result))
error = _one_line(result.error) if (result.error or "").startswith(MYPY_EXIT_PREFIX) else result.error
action = _result_from_findings(error, findings, f"mypy found no issues.{suffix}", f"mypy found {len(findings)} issue(s).{suffix}")
return replace(action, fix_text=fix_text, raw=result.error or result.stderr or "")
```

`format_hint_lines` returns `[f"    {line}" for line in hint.splitlines()]`, or `[]` when `hint` is falsy. `_one_line` returns `" ".join(text.split())`.

## DATA

| Run | `status` | `summary` | `raw` |
|---|---|---|---|
| Clean | `ok` | `mypy found no issues.` | `""` |
| rc 0 with stderr | `ok` | `mypy found no issues. Warning from mypy: <one line>` | stderr |
| rc 1, notes only | `ok` | `mypy found no issues.` | `""` |
| rc 1, notes only, with stderr | `ok` | `mypy found no issues. Warning from mypy: <one line>` | stderr |
| rc 1, errors | `findings` | `mypy found N issue(s).` | `""` |
| rc 1, errors, with stderr (bad `python_version` or `Unrecognized option` plus a type error) | `findings` | `mypy found N issue(s). Warning from mypy: <one line>` | stderr |
| rc 2, errors, no stderr | `findings` | `mypy found N issue(s). mypy exited with code 2, more errors...` | `""` |
| rc 2, errors, with stderr | `findings` | `mypy found N issue(s). mypy exited with code 2, more errors... Warning from mypy: <one line>` | stderr |
| rc 2, plugin crash after errors (`INTERNAL ERROR` on stderr) | `findings` | `mypy found N issue(s). mypy exited with code 2, more errors... Warning from mypy: ... INTERNAL ERROR ...` | stderr |
| New failure | `error` | `mypy exited with code N: <one line>` | full error text |
| Timeout | `error` | unchanged, multi-line | full error text |

## Tests first

Put these in the new `tests/test_toolkit_check_mypy.py`. Use `monkeypatch.setattr("mcp_tools_py.toolkit_checks.run_mypy_check", ...)` returning a built `MypyResult`, run `PythonToolkit().run(ActionRequest(action="check", depth="quick", ...))` as `tests/test_toolkit_check.py` does, and create a `src` directory in `tmp_path`.

- Each row of the DATA table: assert `status`, `summary` contents and `raw`.
- `summary` has no newline for multi-line stderr and for the new error, while `raw` keeps the newlines.
- The timeout error keeps its newlines and its `timeout_seconds` advice in `summary`.
- Notes are excluded: an error plus a note gives 1 finding and "1 issue(s)".
- Hints: `fix_text` has the hint lines indented under the right bullet, and a finding without a hint has none. Use `splitlines()` so found-twice hints with their own indentation are preserved.
- `Finding.message` equals mypy's message alone, and `Finding.key` keeps its `file|code|message` form.
- Hints survive `_merge`: the result comes through the `check` action, so the assertions above run on merged output.
