# Step 1: Adopt the new `describe` and `verify` signatures

## LLM prompt

> Read `pr_info/steps/summary.md` and this file (`pr_info/steps/step_1.md`), then implement this step. Update the test first, then the code. Change only what this step lists. Run the checks below, then make one commit.

## Precondition

The environment needs mcp-coder-utils 8d9baff or later. Check with `mcp__mcp-tools-py__get_library_source("mcp_coder_utils.toolkit.Toolkit")`: `describe` must take only `self`, and `verify` must accept `action`.

If it doesn't, write one line to `pr_info/.blocked.txt` and stop. The workflow can't reinstall from inside.

## WHERE

- `tests/test_toolkit.py`
- `src/mcp_tools_py/toolkit.py`

## WHAT

```python
class PythonToolkit(Toolkit):
    def describe(self) -> ToolkitInfo: ...
    def verify(self, project_dir: Path, action: str | None = None) -> list[VerifyItem]: ...
```

## HOW

Test first, in `tests/test_toolkit.py`, `TestDescribe.test_returns_exact_toolkit_info`:

- Change `PythonToolkit().describe({})` to `PythonToolkit().describe()`.
- This test now fails with a `TypeError` until `describe` changes.

Then in `src/mcp_tools_py/toolkit.py`:

- Remove `from collections.abc import Mapping` and `from typing import Any`. Nothing else in the file uses them, and no configured check reports them.
- `describe`: change the signature and remove the `del config` line. Leave its docstring and return value as they are.
- `verify`: change the signature and add `del action` as the first statement, the repo's convention for unused arguments.
- `verify` docstring: add one sentence after the summary line saying `action` is ignored for now, so every action checks everything. Don't add an `Args:` section.

Don't change `tests/test_toolkit_verify.py`, and don't add a test for `action`.

## ALGORITHM

```
verify(project_dir, action=None):
    del action
    # the existing body is unchanged
```

## DATA

Return values don't change: `describe` returns the same `ToolkitInfo`, and `verify` returns the same `list[VerifyItem]`.

## Checks

All must pass:

- `mcp__mcp-tools-py__run_mypy_check(target_directories=["src", "tests"])`
- `mcp__mcp-tools-py__run_pylint_check`
- `mcp__mcp-tools-py__run_ruff_check`
- `mcp__mcp-tools-py__run_pytest_check(extra_args=["-n", "auto", "-m", "not integration"])`, with `tests/test_toolkit_verify.py` passing unchanged

If mypy still reports an `[override]` error on `describe` or `verify` after these changes, the installed mcp-coder-utils is too old: write one line to `pr_info/.blocked.txt` and stop.

## Commit

Run `mcp__mcp-tools-py__run_format_code`, then stage and commit:

```
fix(toolkit): adopt the new Toolkit signatures (#274)
```
