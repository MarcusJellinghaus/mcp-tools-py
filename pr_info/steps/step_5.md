# Step 5 — wire into server, architecture configs, and docs

Part of the plan in `pr_info/steps/summary.md` (issue #228). Read that file first.

This step has no new runtime logic — it is pure registration/config/doc wiring, so
there is no new unit test to write first; verification is the architecture checks
plus the existing (updated) `test_registrars.py`.

## Precondition

Step 4 is committed: `LibrarySearchTools` exists in `library_search.py`. The current
content of `tach.toml` and `.importlinter` still matches what is quoted below (no
unrelated concurrent edit). If either does not hold, write one line to
`pr_info/.blocked.txt` and stop.

## WHERE / WHAT / HOW

- `src/mcp_tools_py/server.py`: add
  `from mcp_tools_py.library_search import LibrarySearchTools`; in
  `ToolServer.__init__`, after the `InspectTools(self.context).register(self.mcp)`
  line, add `LibrarySearchTools(self.context).register(self.mcp)`.

- `tach.toml`: add a new module block —
  ```toml
  [[modules]]
  path = "mcp_tools_py.library_search"
  layer = "tool_implementation"
  depends_on = [
      { path = "mcp_tools_py.utils" },
      { path = "mcp_tools_py.log_utils" }
  ]
  ```
  and append `{ path = "mcp_tools_py.library_search" }` to the existing
  `mcp_tools_py.server` module's `depends_on` list.

- `.importlinter`: in `[importlinter:contract:layers]`, add
  `mcp_tools_py.library_search` to the tool-implementation layer line (the one
  listing `checker_tools | refactoring | utility_tools | inspect_library |
  formatter`). In `[importlinter:contract:forbidden-imports]`, add
  `mcp_tools_py.library_search` to `forbidden_modules`.

- `tests/test_registrars.py`: `from mcp_tools_py.library_search import
  LibrarySearchTools`; add `LibrarySearchTools(tool_context).register(mcp)` to
  `test_every_registrar_takes_a_tool_context`; bump `EXPECTED_TOOL_COUNT` to `18`
  and update its comment (`# 9 checkers + 1 formatter + 5 refactoring + 1 utility +
  1 inspection + 1 library search.`) and the test's docstring (six registrars, 18
  tools).

- `docs/architecture/architecture.md`: update every occurrence of the tool/registrar
  count to match the new total — the ASCII diagram's tool breakdown, the "Exposes 17
  tools total" sentence (→ 18, "+ 1 library search"), the "9 checker MCP tools"
  bullet area (unaffected), "All five registrars" → "All six registrars", the
  `probe.py` module-overview bullet's subcommand list (`info`/`source`/`locate` →
  `info`/`source`/`locate`/`scope`), and add one Module Overview bullet for
  `library_search.py` modeled on the existing `inspect_library.py` bullet.

## DATA

No new data structures in this step.

## Verification (no new unit tests — this step is wiring)

- `mcp__mcp-tools-py__run_tach_check` passes.
- `mcp__mcp-tools-py__run_lint_imports_check` passes.
- `mcp__mcp-tools-py__run_pytest_check` (unit: `extra_args=["-n", "auto", "-m", "not
  integration"]`) passes, including the updated `test_registrars.py`.
- `mcp__mcp-tools-py__run_pylint_check` and `mcp__mcp-tools-py__run_mypy_check` pass.

## Commit

One commit: `feat(server): register search_library_files and update architecture configs`

## LLM prompt

> Read `pr_info/steps/summary.md` for context, then implement
> `pr_info/steps/step_5.md` only. Make the edits listed under WHERE/WHAT/HOW to
> `src/mcp_tools_py/server.py`, `tach.toml`, `.importlinter`,
> `tests/test_registrars.py` and `docs/architecture/architecture.md`. Run
> `mcp__mcp-tools-py__run_tach_check` and `mcp__mcp-tools-py__run_lint_imports_check`
> and confirm both pass. Run `mcp__mcp-tools-py__run_pylint_check`,
> `mcp__mcp-tools-py__run_pytest_check` (`extra_args=["-n", "auto", "-m", "not
> integration"]`) and `mcp__mcp-tools-py__run_mypy_check` — all must pass. Then run
> `mcp__mcp-tools-py__run_format_code`, stage the changes, and create exactly one
> commit: `feat(server): register search_library_files and update architecture
> configs`. If the precondition above does not hold, write one line to
> `pr_info/.blocked.txt` and stop instead.
