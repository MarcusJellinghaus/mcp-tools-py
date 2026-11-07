# Step 2 — `verify` honours `action`

## LLM prompt

> Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_2.md`.
> Write the tests first, then the implementation. Run pylint, mypy and pytest
> (`extra_args=["-n", "auto", "-m", "not integration"]`), format the code, and
> make exactly one commit.

## WHERE

- `src/mcp_tools_py/toolkit.py` — `PythonToolkit.verify`, new `_tool_item`
- `tests/test_toolkit_verify.py`

## WHAT

```python
def _tool_item(context: ToolContext, tool: str) -> VerifyItem: ...
def verify(self, project_dir: Path, action: str | None = None) -> list[VerifyItem]: ...
```

## HOW

- `_tool_item` is the body of today's loop (ok → `status="ok"`, else
  `status="error"` with `context.unavailable_message(tool)`).
- Imports: `TOOL_MODULES` from `mcp_tools_py.utils.environment_info`;
  `_CHECK_DEPTHS` from `mcp_tools_py.toolkit_checks` (toolkit already imports
  private helpers from there). `CONSOLE_SCRIPT_TOOLS` import goes away if
  unused.
- Remove `del action`. Update the docstring to describe each action.

## ALGORITHM

```
if action is not None and action not in self.describe().actions:
    return [VerifyItem(name=action, status="error", message="Unknown action ...; declared: ...")]
context = _build_context(project_dir)
tools = {"test": ["pytest"], "check": list(_CHECK_DEPTHS["full"])}.get(action, sorted(TOOL_MODULES))
formatter: if action in (None, "format"): try steps = resolve_steps(project_dir) -> ok item;
           if action == "format": tools = sorted({step_tool(s) for s in steps})
           except ValueError -> error item; if action == "format": tools = []
return [_tool_item(context, t) for t in tools] + formatter items
```

## DATA

- `None`: 12 items — mypy, pylint, pytest, deptry, black, isort, ruff, bandit,
  vulture, tach, lint-imports, formatter (ruff once; black/isort stay on ruff
  projects).
- `"format"`: `formatter` + the resolved steps' tools (ruff project →
  `ruff`; black project → `black`, `isort`).
- `"check"`: the 8 `full` tools.
- `"test"`: `pytest`.
- Undeclared: one `error` item.

## Tests (write first)

In `tests/test_toolkit_verify.py`:

- `test_healthy_environment_is_all_ok`: 12 items, names include `deptry`.
- `test_format_on_ruff_project_reports_formatter_and_ruff`: names ==
  `{"formatter", "ruff"}`.
- `test_format_on_black_project_reports_black_and_isort`: pyproject
  `[tool.black]\nline-length = 88\n`; names == `{"formatter", "black", "isort"}`.
- `test_format_without_formatter_is_formatter_error_only`.
- `test_check_reports_every_full_tool`: names == set of the 8 full tools.
- `test_test_reports_pytest`: names == `{"pytest"}`.
- `test_undeclared_action_is_error`: one item, status `"error"`.
- Keep the existing bandit-missing and no-formatter tests passing.
