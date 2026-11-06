# Step 2: Reporting shows the warning, early-stop line and success text

**Commit message:** `fix(mypy): report stderr warnings and early stops`

## LLM prompt

> Read `pr_info/steps/summary.md` and this file, `pr_info/steps/step_2.md`. Step 1 is already committed. Implement this step only, tests first. Run the checks listed in the summary, fix what they report, then make exactly one commit.

## WHERE

- `src/mcp_tools_py/code_checker_mypy/reporting.py`
- `src/mcp_tools_py/checker_tools/__init__.py`
- `src/mcp_tools_py/checker_tools/mypy_tool.py`
- `tests/test_code_checker_mypy/test_reporting.py`
- `tests/test_checker_tools.py`

## WHAT

```python
# reporting.py, next to MYPY_FAILURE_PREFIX
MYPY_SUCCESS_TEXT = "Mypy check completed. No type errors found."

def run_signals(result: MypyResult) -> list[str]: ...
```

## HOW

- `CheckerTools._format_mypy_result(None)` returns `MYPY_SUCCESS_TEXT`, imported from `mcp_tools_py.code_checker_mypy.reporting`. Its behaviour does not change.
- `create_mypy_prompt` still returns `None` when there are no messages.
- `mypy_tool.py` log field: `"issues_found": mypy_prompt is not None and not mypy_prompt.startswith(MYPY_SUCCESS_TEXT)`.

## ALGORITHM

```python
def run_signals(result):
    signals = []
    if result.return_code == 2 and result.messages:
        signals.append("mypy exited with code 2, more errors may appear after these are fixed")
    if result.stderr:
        signals.append(f"Warning from mypy: {result.stderr}")
    return signals
```

```python
# create_mypy_prompt: start of the report, before the header
lines = []
for signal in run_signals(result):
    lines += [signal, ""]

# get_mypy_prompt: replaces the final return
prompt = create_mypy_prompt(result, max_issues=max_issues)
if prompt is None and result.stderr:
    return "\n\n".join([MYPY_SUCCESS_TEXT, *run_signals(result)])
return prompt
```

Update the `get_mypy_prompt` docstring's `Returns`, which says "None if no issues": it returns the success text plus the warning for a passing rc 0 run with stderr, and `None` only for a passing run without stderr.

## DATA

- `run_signals` returns 0 to 2 strings, early-stop line first. It returns `[]` for any error result, because those have `messages=[]` and `stderr=None`.
- `get_mypy_prompt` for rc 0 with stderr returns `"Mypy check completed. No type errors found.\n\nWarning from mypy: <text>"`.

## Tests first

**`test_reporting.py`**
- `run_signals`: none, early stop only, warning only, both in order, and rc 2 with no messages gives no early-stop line.
- `create_mypy_prompt`:
  - rc 2 with messages starts with the early-stop line.
  - rc 1 with stderr shows the warning.
  - A notes-only run with stderr shows the warning.
  - Both signals appear at `max_issues=0`.
  - The existing exact-match tests for runs without signals still pass unchanged.
- `get_mypy_prompt` with a patched `execute_command`:
  - rc 0 with stderr gives success plus warning.
  - rc 0 without stderr gives `None`.
  - rc 1 with no output gives `MYPY_FAILURE_PREFIX` and `mypy exited with code 1: no output`.

**`test_checker_tools.py`:** following the existing pattern of patching `get_mypy_prompt`, also patch `mcp_tools_py.checker_tools.mypy_tool.logger`, and assert from the `extra` of the "Mypy check completed" call that `issues_found` is `False` for success plus warning and `True` for a report.
