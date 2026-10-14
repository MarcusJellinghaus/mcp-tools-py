# Step 3: `check` action — quick/standard (mypy, pylint) + generic merge helpers

See `pr_info/steps/summary.md` for full architectural context.

## WHERE

- Modify `src/mcp_tools_py/toolkit.py`: add `_merge`, the check dispatch
  tables, `_run_mypy`, `_run_pylint`, `_run_check`; wire into
  `PythonToolkit.run()`.
- Extend `tests/test_toolkit.py`.

## WHAT

```python
_STATUS_RANK: dict[str, int] = {"skipped": 0, "ok": 1, "findings": 2, "error": 3}

def _merge(results: list[ActionResult]) -> ActionResult: ...

_CHECK_DEPTHS: dict[str, tuple[str, ...]] = {
    "quick": ("mypy",),
    "standard": ("mypy", "pylint"),
}  # "full" added in step 4

_CHECK_RUNNERS: dict[str, Callable[[ToolContext], ActionResult]] = {
    "mypy": _run_mypy,
    "pylint": _run_pylint,
}  # extended in step 4

def _run_mypy(context: ToolContext) -> ActionResult: ...
def _run_pylint(context: ToolContext) -> ActionResult: ...
def _run_check(context: ToolContext, depth: str) -> ActionResult: ...
```

## HOW

- Import `run_mypy_check` from `mcp_tools_py.code_checker_mypy.runners`,
  `get_pylint_results` from `mcp_tools_py.code_checker_pylint.runners`.
- Import `resolve_target_directories` from `mcp_tools_py.utils.project_config`
  (both mypy and pylint need resolved target directories, same as their
  `checker_tools/*` registrars).
- `describe()`'s `llm_permissions["check"]` already names the tools per
  depth (step 1); `_CHECK_RUNNERS`/`_CHECK_DEPTHS` here are `run()`'s mirror
  of that same mapping — keep the tool-name strings (`"mypy"`, `"pylint"`)
  identical to `ToolContext.is_tool_available`'s existing `ToolName` values
  so no translation layer is needed.
- In `PythonToolkit.run()`, add `elif request.action == "check": return _run_check(context, request.depth)`.

## ALGORITHM (`_run_check`)

```
tools = _CHECK_DEPTHS[depth]                       # KeyError for an undeclared depth is a bug, let it raise
for tool in tools: if not context.is_tool_available(tool): return error (short-circuit, no partial run)
results = [_CHECK_RUNNERS[tool](context) for tool in tools]
return _merge(results)
```

## ALGORITHM (`_merge`)

```
worst = max(results, key=lambda r: _STATUS_RANK[r.status])
findings = [f for r in results for f in r.findings]
summary = "; ".join(r.summary for r in results)
raw = "\n\n".join(r.raw for r in results if r.raw)
return ActionResult(status=worst.status, summary=summary, findings=findings, raw=raw,
                     fix_text=_fix_text(findings) if findings else "")
```

(`findings` non-empty on the merged result only ever coincides with
`status in ("error", "findings")` because `"findings"` already outranks
`"ok"`/`"skipped"` in `_STATUS_RANK` — no extra guard needed, `ActionResult`'s
own validation would otherwise reject it.)

## DATA

- `_run_mypy`: `result = run_mypy_check(...)`; `result.error` → error branch
  of `_result_from_findings`; else `Finding(key=f"{m.file}|{m.code}|{m.message}", message=m.message, path=m.file, rule=m.code, severity=m.severity)`
  for each `m` in `result.messages`.
- `_run_pylint`: `result = get_pylint_results(...)`; `result.error` → error;
  else `Finding(key=f"{m.path}|{m.message_id}|{m.message}", message=m.message, path=m.path, rule=m.message_id)`
  for each `m` in `result.messages`.
- Both reuse `_result_from_findings` from step 1 for the final
  `ActionResult` assembly.

## Tests (write first)

- `check@quick` on a clean project → `ok` (mypy only).
- `check@quick` on a project with a type error → `findings`, one `Finding`
  keyed `path|code|message`.
- `check@standard` merges mypy + pylint: a pylint-only issue still produces
  `findings` even when mypy is clean; a project failing both produces
  findings from both tools concatenated.
- mypy or pylint reported unavailable (patch `ToolContext.is_tool_available`)
  → `check@quick`/`check@standard` returns `error`, not `findings`, and the
  other tool is never invoked (assert the runner mock was not called).
- `_merge` unit-tested directly: `[ok, ok] -> ok`; `[ok, findings] -> findings`
  with concatenated findings; `[findings, error] -> error`; any status with
  `skipped` present but nothing worse stays at the worse of the two.

---

## LLM Prompt

Read `pr_info/steps/summary.md` for the overall architecture, then implement
**Step 3** exactly as described in `pr_info/steps/step_3.md`.

Follow TDD: write the tests listed under "Tests" in `tests/test_toolkit.py`
first, confirm they fail for the right reason, then implement `_merge`,
`_run_mypy`, `_run_pylint`, `_run_check`, and the dispatch tables in
`src/mcp_tools_py/toolkit.py`, and wire `_run_check` into `PythonToolkit.run()`.
Run pylint, pytest, and mypy via the MCP tools and fix all issues before
finishing.
