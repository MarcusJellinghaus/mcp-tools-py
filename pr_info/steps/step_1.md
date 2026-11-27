# Step 1 — `tool` parameter on `resolve_target_directories`, passed at every call site

Read [summary.md](summary.md) first. This step adds the parameter only.
Behaviour does not change.

## LLM prompt

> Implement Step 1 of `pr_info/steps/summary.md` as described in
> `pr_info/steps/step_1.md`. TDD: first write `tests/test_target_directories_call_sites.py`
> and update the pinned tests, run them and see them fail, then change the resolver
> signature and the 13 call sites. Run `run_format_code`, then pylint, pytest
> (`markers=["not integration"]`) and mypy; all must pass. Produce exactly one commit.

## WHERE

- `src/mcp_tools_py/utils/project_config.py`
- Call sites (13): `formatter/formatter_tools.py`, `checker_tools/{ruff_check,ruff_fix,pylint,mypy,vulture,bandit}_tool.py`,
  `toolkit.py` (`_run_format`), `toolkit_checks.py` (`_run_mypy`, `_run_pylint`,
  `_run_vulture`, `_run_ruff`, `_run_bandit`)
- Tests: new `tests/test_target_directories_call_sites.py`; update
  `tests/test_project_config.py` (`TestResolveTargetDirectories`, 4 calls) and
  `tests/test_formatter_tools.py` (`TestTargetDirectories`, 2 `assert_called_once_with`)

## WHAT

```python
# project_config.py
TargetTool = Literal["formatter", "ruff", "pylint", "mypy", "vulture", "bandit"]

def resolve_target_directories(
    project_dir: str,
    target_directories: list[str] | None,
    tool: TargetTool,
) -> list[str] | str:
```

In this step the body is unchanged except for `del tool`, which keeps vulture
quiet the same way the toolkit runners do with `del depth`. Document `tool` in the
docstring as "the program the directories are for".

Call sites pass `tool` **positionally as the third argument**:

| Call site | `tool` |
|---|---|
| `run_format_code` (formatter_tools.py), `_run_format` (toolkit.py) | `"formatter"` |
| `run_ruff_check`, `run_ruff_fix`, `_run_ruff` | `"ruff"` |
| `run_pylint_check`, `_run_pylint` | `"pylint"` |
| `run_mypy_check`, `_run_mypy` | `"mypy"` |
| `run_vulture_check`, `_run_vulture` | `"vulture"` |
| `run_bandit_check`, `_run_bandit` | `"bandit"` |

`toolkit.py` is 749 lines (limit 750). Its edit must stay on one line:
`dirs = resolve_target_directories(str(project_dir), None, "formatter")`. If the
file would grow past 750 lines, write one line to `pr_info/.blocked.txt` and stop.

## HOW (tests)

`tests/test_target_directories_call_sites.py` uses the `tool_context` fixture from
`tests/conftest.py`, where every tool is available. `_SENTINEL = "Error resolving
target directories: sentinel"`.

1. **MCP tools.** Parametrise over `(tool function name, module to patch, expected
   tool)`:
   - `run_format_code`: `mcp_tools_py.formatter.formatter_tools`, `"formatter"`.
     Register with `FormatterTools`, and first write
     `[tool.mcp-tools-py]\nformatter = "ruff"\n` to
     `tool_context.project_dir / "pyproject.toml"`.
   - `run_ruff_check`: `mcp_tools_py.checker_tools.ruff_check_tool`, `"ruff"`.
   - `run_ruff_fix`: `…ruff_fix_tool`, `"ruff"`.
   - `run_pylint_check`: `…pylint_tool`, `"pylint"`.
   - `run_mypy_check`: `…mypy_tool`, `"mypy"`.
   - `run_vulture_check`: `…vulture_tool`, `"vulture"`.
   - `run_bandit_check`: `…bandit_tool`, `"bandit"`.

   Register the checker tools with `CheckerTools`. Capture the functions with a
   `MagicMock` whose `tool.return_value` records `fn.__name__`, the same pattern as
   `_capture_tool` in `tests/test_checker_tools.py`. Patch
   `<module>.resolve_target_directories` with `return_value=_SENTINEL` and call the
   function with no arguments. Assert `_SENTINEL in result` and
   `mock.call_args.args == (str(tool_context.project_dir), None, expected)`.
2. **Toolkit check runners.** Parametrise `name` over `mypy, pylint, vulture, ruff,
   bandit`. Patch `mcp_tools_py.toolkit_checks.resolve_target_directories` with
   `return_value=_SENTINEL` and call `_CHECK_RUNNERS[name](tool_context, "full")`.
   Assert `status == "error"`, `summary == _SENTINEL`, and that the call args are
   `(str(project_dir), None, name)`.
3. **Toolkit format.** Write the same `formatter = "ruff"` pyproject. Patch
   `mcp_tools_py.toolkit.resolve_target_directories` and call
   `_run_format(tool_context, "check")` (import from `mcp_tools_py.toolkit`). Assert
   status `"error"`, summary `_SENTINEL`, and the third arg `"formatter"`.

Existing tests: add `"mypy"` as the third argument to the four
`resolve_target_directories(...)` calls in `tests/test_project_config.py`. In
`tests/test_formatter_tools.py`, the two `assert_called_once_with` calls get
`"formatter"` as their last argument.

## ALGORITHM

None. This step only threads the parameter through.

## DATA

Return type unchanged: `list[str] | str`.
