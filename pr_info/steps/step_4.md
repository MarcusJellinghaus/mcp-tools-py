# Step 4: `check@full` — vulture, lint-imports, tach, ruff, bandit

See `pr_info/steps/summary.md` for full architectural context.

## WHERE

- Modify `src/mcp_tools_py/toolkit.py`: add `_run_vulture`, `_run_lint_imports`,
  `_run_tach`, `_run_ruff`, `_run_bandit`; extend `_CHECK_DEPTHS` and
  `_CHECK_RUNNERS` from step 3 with the `"full"` depth and these five tools.
- Extend `tests/test_toolkit.py`.

## WHAT

```python
_CHECK_DEPTHS["full"] = ("mypy", "pylint", "vulture", "lint-imports", "tach", "ruff", "bandit")
_CHECK_RUNNERS.update({
    "vulture": _run_vulture,
    "lint-imports": _run_lint_imports,
    "tach": _run_tach,
    "ruff": _run_ruff,
    "bandit": _run_bandit,
})

def _run_vulture(context: ToolContext) -> ActionResult: ...
def _run_lint_imports(context: ToolContext) -> ActionResult: ...
def _run_tach(context: ToolContext) -> ActionResult: ...
def _run_ruff(context: ToolContext) -> ActionResult: ...
def _run_bandit(context: ToolContext) -> ActionResult: ...
```

`_run_check` and `_merge` from step 3 are unchanged — adding the `"full"`
entry to the two tables is all `check@full` needs; the short-circuit and
worst-status-wins merge already generalize.

## HOW

- `_run_vulture`: import `run_vulture_check` from `mcp_tools_py.code_checker_vulture`,
  same binary/whitelist resolution `vulture_tool.py` uses
  (`context.tool_environment.binary("vulture")`, `context.vulture_whitelist`).
- `_run_lint_imports`: import `run_lint_imports_check_impl` from
  `mcp_tools_py.code_checker_lint_imports`.
- `_run_tach`: import `execute_command` from `mcp_tools_py.utils.subprocess_runner`
  and build the **same** `[tach_binary, "check", "--output", "json"]` command
  `code_checker_tach.runners.run_tach_check` builds — call `execute_command`
  directly instead of that runner, because `run_tach_check` discards the
  return code needed for status. Still call `run_tach_check` itself (or
  reuse its text formatting) for the finding's message text, so the output
  the LLM sees matches `mcp__mcp-tools-py__run_tach_check`'s own phrasing.
- `_run_ruff`: per the issue's explicit decision, do **not** call
  `code_checker_ruff.runners` (prose only). Build the ruff command directly
  (`[ruff_binary, "check", "--output-format", "json", *target_directories]`,
  binary from `context.tool_environment.binary("ruff")`), run it with
  `execute_command`, then parse with
  `mcp_tools_py.utils.ruff_parsing.parse_ruff_json_output`.
- `_run_bandit`: import `run_bandit_check_impl` from
  `mcp_tools_py.code_checker_bandit.runners` (already structured —
  `BanditResult.error`/`.messages`).
- All five resolve target directories via `resolve_target_directories`
  (step 3's import) where the underlying runner needs them (vulture, ruff,
  bandit); tach and lint-imports take none.

## ALGORITHM (degraded tools — single finding per tool+depth)

Keyed by tool name, not action name: vulture, lint-imports and tach all run
under the `check` action, so a key of `action+depth` (e.g. `check|full`)
would be identical for all three and their findings would collide within
one `check@full` result. `tool+depth` (`vulture|full`, `lint-imports|full`,
`tach|full`) keeps them distinct.

```
# vulture
output = run_vulture_check(binary, project_dir, dirs, whitelist_path=..., timeout_seconds=...)
output starts with "vulture timed out" or "vulture failed to run:" -> error
output == "vulture produced no output." -> ok
else -> one Finding(key=f"vulture|{depth}", message=output)

# lint-imports
report = run_lint_imports_check_impl(binary, project_dir, ..., python_executable=...)
first "=== ... ===" line contains "ERROR" -> error; "BROKEN" -> one Finding(key=f"lint-imports|{depth}", message=report); "PASSED" -> ok

# tach
result = execute_command([tach_binary, "check", "--output", "json"], cwd=project_dir, timeout_seconds=...)
result.timed_out or result.execution_error -> error
result.return_code == 0 -> ok
else -> one Finding(key=f"tach|{depth}", message=<tach's own output text>)
```

`_run_ruff` and `_run_bandit` reuse `_result_from_findings` (step 1) exactly
like `_run_mypy`/`_run_pylint` in step 3, since they expose structured
per-location data.

## DATA

- `_run_ruff`: `messages, parse_error = parse_ruff_json_output(stdout, project_dir)`;
  `parse_error` → error; else `Finding(key=f"{m.filename}|{m.code}|{m.message}", message=m.message, path=m.filename, rule=m.code)`
  for each `m`.
- `_run_bandit`: `result = run_bandit_check_impl(...)`; `result.error` → error;
  else `Finding(key=f"{m.filename}|{m.test_id}|{m.issue_text}", message=m.issue_text, path=m.filename, rule=m.test_id, severity=m.issue_severity)`
  for each `m` in `result.messages`.
- Need `depth` threaded into `_run_vulture`/`_run_lint_imports`/`_run_tach`
  for the degraded key — either pass `depth` as a parameter (update their
  signatures to `(context, depth)`) or close over it; prefer the explicit
  parameter for consistency with the other `_run_*` functions, and update
  `_CHECK_RUNNERS`' call site in `_run_check` accordingly (all seven
  functions then take `(context, depth)` — adjust `_run_mypy`/`_run_pylint`
  signatures too, even though they don't use `depth`, so the dispatch table
  stays uniform).

## Tests (write first)

- `check@full` with every tool clean → `ok`.
- `check@full` with a vulture-only finding (unused function in a fixture) →
  `findings`, single `Finding` keyed `vulture|full`.
- `check@full` with a tach violation (or a mocked `execute_command` return
  code of 1) → `findings`, single `Finding` keyed `tach|full`; a mocked
  timeout/execution error → `error`.
- `check@full` with a lint-imports contract violation → `findings` with
  `BROKEN` in the message; a config error → `error`.
- `check@full` with a ruff violation → `findings`, one `Finding` per
  `path|code|message`.
- `check@full` with a bandit finding → `findings`, one `Finding` per
  `path|test_id|message`.
- Any one of the five reported unavailable → `check@full` returns `error`
  and none of the seven runners are invoked (short-circuit still holds with
  the full seven-tool list).
- `check@full` with findings from two different tools (e.g. mypy + ruff)
  merges both into one `findings` result via `_merge`.

---

## LLM Prompt

Read `pr_info/steps/summary.md` for the overall architecture, then implement
**Step 4** exactly as described in `pr_info/steps/step_4.md`.

Follow TDD: write the tests listed under "Tests" in `tests/test_toolkit.py`
first, confirm they fail for the right reason, then implement the five new
`_run_*` functions in `src/mcp_tools_py/toolkit.py` and extend
`_CHECK_DEPTHS`/`_CHECK_RUNNERS` from step 3 with the `"full"` depth. Run
pylint, pytest, and mypy via the MCP tools and fix all issues before
finishing.
