# Step 2: `format` action (apply / check)

See `pr_info/steps/summary.md` for full architectural context.

## WHERE

- Modify `src/mcp_tools_py/toolkit.py`: add `_run_format`, wire it into
  `PythonToolkit.run()`.
- Extend `tests/test_toolkit.py`.

## WHAT

```python
def _run_format(context: ToolContext, depth: str) -> ActionResult: ...
```

`depth` is `"apply"` or `"check"` (not quick/standard/full — `format`'s own
depth names, already declared in step 1's `describe()`).

## HOW

- Import `resolve_steps`, `validate_steps`, `step_tool`, `run_format_code`
  from `mcp_tools_py.formatter.runner`.
- Import `resolve_target_directories` from `mcp_tools_py.utils.project_config`.
- In `PythonToolkit.run()`, add `elif request.action == "format": return _run_format(context, request.depth)`.

## ALGORITHM

```
check_only = depth == "check"
steps = resolve_steps(project_dir); validate_steps(steps)   # ValueError -> error
for step in steps: if tool unavailable -> error (context.unavailable_message)
dirs = resolve_target_directories(project_dir, None)          # str return -> error
results = run_format_code(interpreter, project_dir, dirs, steps, check_only,
                           timeouts={step: context.resolve_timeout(step_tool(step)) for step in steps},
                           environment=context.tool_environment)
broken = any(r.unparsable_files or (not r.success and not check_only) for r in results.values())
broken -> error; else check_only and any files_changed -> findings (one per path); else -> ok
```

`raw` is always set to the joined `output` of every step's `FormatterResult`
(`"\n\n".join(r.output for r in results.values())`), regardless of status.

## DATA

- `changed = sorted({p for r in results.values() for p in r.files_changed})`.
- `Finding(key=f"format|check|{path}", message=f"{path} needs reformatting", path=path)`
  for each `path` in `changed`, only when `check_only` and `changed` is
  non-empty.
- `ActionResult(status, summary, findings=[...], fix_text=..., raw=...)` via
  `_result_from_findings` (from step 1) where it fits, or constructed
  directly when the `error` branch comes from a caught `ValueError` or an
  unavailable tool rather than a `.error` attribute.

## Tests (write first)

- `format@apply` on a project whose files are already formatted → `ok`,
  `raw` non-empty.
- `format@apply` where resolving the formatter raises `ValueError` (no
  `[tool.black]`/`[tool.ruff.format]` and no `[tool.mcp-tools-py] formatter`)
  → `error`.
- `format@check` on a deliberately unformatted fixture file → `findings`,
  one `Finding` per changed path, non-empty `fix_text`.
- A formatter tool reported unavailable (patch `ToolContext.is_tool_available`
  or use a project dir misconfiguration) → `error`, not `findings`.

---

## LLM Prompt

Read `pr_info/steps/summary.md` for the overall architecture, then implement
**Step 2** exactly as described in `pr_info/steps/step_2.md`.

Follow TDD: write the tests listed under "Tests" in `tests/test_toolkit.py`
first, confirm they fail for the right reason, then implement `_run_format`
in `src/mcp_tools_py/toolkit.py` and wire it into `PythonToolkit.run()`. Run
pylint, pytest, and mypy via the MCP tools and fix all issues before
finishing.
