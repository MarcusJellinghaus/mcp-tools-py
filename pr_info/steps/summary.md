# Implementation Summary: Toolkit Interface (#245)

## Goal

Make mcp-tools-py discoverable by mcp-coder as the Python toolkit, via the
`Toolkit` abstract base class from `mcp-coder-utils` (`mcp_coder_utils.toolkit`).

## Architecture / Design

### One new module, table-driven

All new code lives in one module: `src/mcp_tools_py/toolkit.py`, exporting
`PythonToolkit(Toolkit)`. It never imports `checker_tools/*` (those produce
LLM-facing prose, not structured data) — only the `code_checker_*`,
`formatter/`, and `utils/` modules that already return structured results
(`MypyResult`, `PylintResult`, `BanditResult`, `FormatterResult`,
`PytestReport`, `RuffMessage`, plus the existing `ToolContext` for
availability/timeouts).

`run(request: ActionRequest) -> ActionResult` builds one `ToolContext` per
call (`PythonEnvironment.resolve()`, same convention the old
`mcp_coder/mcp_tools_py.py` shim used — mcp-coder runs inside the project's
own venv, so no interpreter path travels through `ActionRequest`), then
dispatches on `request.action`:

- **`test`** (`quick`/`standard`/`full`): `code_checker_pytest.runners.check_code_with_pytest`.
  `quick` passes `markers=["not integration"]`; `standard`/`full` pass no
  marker filter; `full` additionally measures coverage (mirroring
  `run_pytest_check(coverage=True)`) and appends the digest to
  `ActionResult.raw` — informational only, never changes `status`.
- **`format`** (`apply`/`check`): `formatter.runner.run_format_code`, with
  `check_only = (depth == "check")`. A `check_only=True` non-zero exit is a
  **finding** ("would reformat"); a real tool failure (`unparsable_files`,
  or a non-zero exit in apply mode) is an **error**.
- **`check`** (`quick`/`standard`/`full`): a small per-tool dispatch table
  (tool name → run function, and tool name → MCP tool name) drives both
  `run()` and `describe()`'s `llm_permissions`, so the two can't drift apart.
  `quick` = mypy; `standard` = mypy+pylint; `full` adds vulture,
  lint-imports, tach, ruff, bandit. Before running anything at a depth,
  every tool in that depth's list is checked for availability
  (`ToolContext.is_tool_available`); if any is missing, the whole action
  returns `status="error"` immediately (never partial `findings`).

### Two small generic helpers (not one per tool)

- `_result_from_findings(error, findings, ok_summary, findings_summary) -> ActionResult`:
  the common `error` / `findings` / `ok` assembly, reused by every check tool
  that already exposes `.error` + a messages list (mypy, pylint, ruff,
  bandit) and by `test`/`format`.
- `_merge(results: list[ActionResult]) -> ActionResult`: worst-status-wins
  (`error` > `findings` > `ok` > `skipped`) with findings concatenated.
  Reused for both `check@standard` and `check@full` — no separate merge
  logic per depth.

`ActionResult.fix_text` is built generically from the merged `findings` list
(one bullet line per finding: path/rule/message) rather than reusing each
checker's bespoke prose generator (`create_mypy_prompt`, pylint's grouped
prompt, etc.) — this is what the `fix.check` prompt fragment inlines, in
place of the old `[mypy_output]` placeholder.

### Finding keys

- pytest: node id.
- mypy, pylint, ruff, bandit: `path+rule+message` (each already a `NamedTuple`
  with those fields).
- vulture, lint-imports, tach: no stable per-location keys today, so each
  gets **one** degraded `Finding` keyed by `action+depth`:
  - vulture: its existing runner already returns deterministic sentinel text
    (`"vulture produced no output."` / `"...timed out..."` /
    `"...failed to run:..."`) — matched directly, no new code.
  - lint-imports: its existing runner already emits a parseable
    `=== PASSED/BROKEN/ERROR ===` header by design — read directly, no new
    code.
  - tach: the one real exception. Its runner (`code_checker_tach.runners.run_tach_check`)
    discards the subprocess return code entirely, so pass/fail cannot be
    recovered from its text output. `toolkit.py` calls `execute_command`
    directly with the same command tach's runner builds, reading only the
    return code for status; the runner's own text is still used as the
    finding's message.
- `format@check`: one `Finding` per file path that would be reformatted
  (deduplicated across formatter steps), since formatting has no
  rule/code concept.

### `verify()`

Reuses `ToolContext.is_tool_available`/`unavailable_message` (already used by
every `checker_tools/*` registrar) to build one `VerifyItem` per tool, plus
one for formatter resolution (`formatter.runner.resolve_steps`).

### `describe()` / `prompt_fragments()`

- `params_schema`: `{"type": "object", "properties": {}, "additionalProperties": False}`
  — empty and closed, no configurable params for v1.
- `llm_permissions`: built from the same dispatch tables `run()` uses, so
  every MCP tool actually invoked at a depth is listed and nothing drifts.
- `prompt_fragments()` returns `language_context`, `check_instructions`, and
  `fix.check` — the Mypy Fix prompt, moved here from
  `mcp_coder/src/mcp_coder/prompts/prompts.md`, with its `[mypy_output]`
  placeholder line dropped (the actual output now travels via
  `ActionResult.fix_text`). The copy in mcp-coder's `prompts.md` is left
  alone — removing it is mcp_coder#1197's job, not this issue's.

## Files created

| File | Purpose |
|---|---|
| `src/mcp_tools_py/toolkit.py` | `PythonToolkit` and all helpers above |
| `tests/test_toolkit.py` | Unit tests, extended across all 5 steps |

## Files modified

| File | Change |
|---|---|
| `pyproject.toml` | `[project.entry-points."mcp_coder.toolkits"]` → `mcp-tools-py = "mcp_tools_py.toolkit:PythonToolkit"` |
| `docs/upgrade-notes.md` | New entry noting the toolkit interface and the `mcp-coder-utils` dependency |

No existing module under `code_checker_*`, `formatter/`, `utils/`, or
`checker_tools/` is modified — `toolkit.py` only calls their existing public
functions.

## Step overview

1. Skeleton: entry point, `describe()` (final, complete), `prompt_fragments()`,
   `_build_context`, and `run()` for the `test` action only.
2. `run()` for the `format` action (`apply`/`check`).
3. `run()` for `check@quick`/`check@standard` (mypy, pylint) + the two
   generic helpers (`_result_from_findings`, `_merge`) + the check dispatch
   tables.
4. `run()` for `check@full`'s five extra tools (vulture, lint-imports, tach,
   ruff, bandit), extending the step-3 dispatch tables.
5. `verify()` + `docs/upgrade-notes.md`.

Each step is one commit: tests in `tests/test_toolkit.py` first, then the
matching code in `src/mcp_tools_py/toolkit.py`, then pylint/pytest/mypy all
passing.
