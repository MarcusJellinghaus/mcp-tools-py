# Summary — Bring PythonToolkit in line with mcp-coder's workflows (#272)

## Goal

mcp_coder#1195 will route mcp-coder's workflows through `PythonToolkit` with no
behaviour change. `PythonToolkit` currently does less than those workflows, so
this issue closes the gap:

- finish the mcp-coder-utils#55 contract (`verify(action)`, `run` rejecting
  undeclared actions/depths),
- add `test@unattended`,
- set depth-based pytest timeouts,
- turn failed collectors into findings,
- make mypy findings errors-only,
- put locations into `fix_text`.

#274 (adopting the new `describe`/`verify` signatures) is merged as commit
`fc870d2` (#275); `verify(project_dir, action=None)` already exists and ignores
`action`.

## Architectural / design changes

All changes stay inside the two toolkit modules; no runner, parser or MCP tool
changes, and no new module.

| Area | Before | After |
|---|---|---|
| `run` dispatch | Unknown action raises `NotImplementedError`; unknown depth runs something or raises `KeyError` | `describe().actions` is the single source of truth; undeclared action/depth → `ActionResult(status="error")`, checked **before** `_build_context` |
| `verify(action)` | `action` ignored; 11 items, no deptry | `None` → every tool in `TOOL_MODULES` (incl. deptry) + `formatter` = 12; `"format"` → formatter + tools of the resolved steps; `"check"` → `_CHECK_DEPTHS["full"]`; `"test"` → pytest; undeclared → one `error` item |
| `test` depths | `quick`, `standard`, `full` | adds `unattended`: marker filter from one constant `UNATTENDED_EXCLUDED_MARKERS`, plus `-o strict_markers=false` |
| Prompt fragments | 3 keys | adds `check_instructions.unattended`, generated from the same constant |
| pytest timeout | 300 s default at every depth | `standard`/`unattended`/`full` default to 1800 s by putting it in `ToolContext.check_timeout` (the `cli_timeout` slot), so a project's `pytest-timeout`/`check-timeout` still wins |
| Failed collectors | Real run → `error` via the `known` gate; never findings | One `Finding` per failed collector (keyed by node id, deduplicated); all xdist "Different tests were collected" reports collapse into one finding with a fixed key; computed **before** the `known` gate |
| mypy findings | Every non-note message; `raw` = error or stderr | Only `severity == "error"`; `raw` = `MypyResult.raw_output` (empty when the runner returned early) |
| `fix_text` | `- path: rule: message` | `- path:line: rule: message` for check tools, `- nodeid: message` for tests, via one optional `location` argument on the existing helpers |

### Helper changes (KISS)

- `_finding_line(finding, location: str | None = None)` — `location` replaces
  `finding.path` in the bullet when given.
- `_result_from_findings(..., locations: list[str | None] | None = None)` —
  optional, parallel to `findings`; omitted → unchanged output, so
  `_run_format`, `_merge`'s fallback and `TestMerge` are untouched.
- `_tool_item(context, tool) -> VerifyItem` — the existing verify loop body.
- `_collector_findings(report) -> list[Finding]` and
  `_is_collection_error(report, verdict) -> bool` — the only new logic
  helpers; failed collectors bypass the `known` gate only for an ERROR caused
  by collection errors.
- New constants in `toolkit.py`: `UNATTENDED_EXCLUDED_MARKERS`,
  `_STRICT_MARKERS_OFF`, `_LONG_TEST_TIMEOUT`, `_XDIST_KEY`.

## Files modified

No new source files or folders.

| File | Change |
|---|---|
| `src/mcp_tools_py/toolkit.py` | `run` validation, `verify(action)`, `_tool_item`, `unattended` depth + constant + fragment, depth timeout, `_collector_findings`, test-name locations |
| `src/mcp_tools_py/toolkit_checks.py` | `location`/`locations` arguments, line locations in pylint/ruff/bandit/deptry/mypy runners, mypy errors-only + `raw_output` |
| `tests/test_toolkit.py` | `TestDescribe`, `TestPromptFragments`, `_finding_line`/`_result_from_findings` location tests |
| `tests/test_toolkit_test.py` | unknown action/depth, timeouts, unattended, collector findings, flipped verdict tests |
| `tests/test_toolkit_verify.py` | per-action verify, 12 items |
| `tests/test_toolkit_check.py` | line locations for pylint/ruff/bandit/deptry |
| `tests/test_toolkit_check_mypy.py` | errors-only, `raw` = `raw_output`, located fix_text |
| `tests/test_toolkit_saved_coverage.py` | xdist collector test flips to `findings` |

## Steps

1. `run` returns `error` for an undeclared action or depth.
2. `verify` honours `action`.
3. mypy: errors-only findings, `raw` = mypy's raw output.
4. Locations in `fix_text` (check tools: lines; test: node ids).
5. `test@unattended` (depth, marker filter, `-o strict_markers=false`, prompt fragment).
6. Depth-based pytest timeouts.
7. Failed collectors become findings.

## Out of scope

- `test@quick`'s `not integration` filter (mcp_coder#1389).
- Any marker override param — `params_schema` stays closed.
- mcp-coder's mypy wrapper and its unrecognised-outcome branch.
- `_merge`'s fix_text joining (stays as is).
