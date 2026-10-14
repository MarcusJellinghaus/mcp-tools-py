# search_library_files — implementation summary

Implements GitHub issue #228: a new MCP tool, `search_library_files`, that greps/globs
inside an *installed* package's source files (anywhere in the project's configured
Python environment — including stdlib), as the inverse of `get_library_source`
("show me this symbol" vs. "which file mentions this string").

## Architectural / design changes

- **New registrar module**: `mcp_tools_py.library_search`, sitting beside
  `inspect_library` in the tool-implementation layer. No shared implementation with
  `get_library_source` — a fresh, small search core, not a promotion of
  `mcp-workspace`'s project/gitignore-shaped `search_files` core.
- **Two-phase execution**, per #217's "resolve Python names through
  `ToolContext.environment`" invariant:
  1. **Scope resolution** (target environment, via subprocess): turn the mandatory
     `scope` argument ("mypy", "mypy.config_parser", or "stdlib") into one directory.
     `scope="stdlib"` is served from the already-cached one-shot environment probe
     (`EnvironmentInfo.stdlib`, a new field); any other scope runs a new, uncached
     `probe.py scope NAME` subcommand — uncached because where a package lives can
     change while the server runs (same rationale as the existing `locate_packages`).
  2. **File search** (server process, no subprocess): walk the resolved directory,
     filter by glob, search content by regex — plain local filesystem work.
- **`probe.py` (stdlib-only target script)** gains:
  - a `stdlib` field in the `info` blob (`sysconfig.get_paths()["stdlib"]`)
  - a new `scope NAME` subcommand, deliberately separate from `locate` (which answers
    a different question — the PYTHONPATH root, not the package's own directory)
- **`environment_info.py`** gains `EnvironmentInfo.stdlib: str = ""` (defaulted, so
  existing callers are unaffected) and `resolve_scope(interpreter, scope) ->
  ScopeResolution`, a small dataclass (`directory` xor `error`) — not the
  `tuple | str` union `locate_packages` uses, since scope resolution has no
  PYTHONPATH-safety classification to report.
- **Result shape** mirrors `mcp_workspace.search_files` (`mode`, `details`/`files`,
  `total_matches`/`total_files`, `truncated`, optional `note`/`skipped_files`/
  `matched_files`), plus one addition: a top-level `scope_root` (absolute path),
  since the matched files live outside the project and the caller needs an absolute
  path to read them with the native `Read` tool.
- Two simplifications versus `search_files`, deliberately **not** carried over
  (neither is required by the issue): no "must supply glob or pattern" validation
  (scope already bounds the search size — the issue's whole rationale for making it
  mandatory), and no brace-detection `glob_note` helper text.
- `server.py` registers `LibrarySearchTools` as a sixth registrar.
- `tach.toml` and `.importlinter` get the new module added to the existing
  tool-implementation layer / forbidden-imports lists — no new contracts.

## Files created

- `src/mcp_tools_py/library_search.py`
- `tests/test_library_search.py`

## Files modified

- `src/mcp_tools_py/utils/target_scripts/probe.py` — `stdlib` info field, `scope` subcommand
- `src/mcp_tools_py/utils/environment_info.py` — `EnvironmentInfo.stdlib`, `ScopeResolution`, `resolve_scope`
- `src/mcp_tools_py/server.py` — register `LibrarySearchTools`
- `tach.toml` — new `mcp_tools_py.library_search` module entry; extend `server`'s `depends_on`
- `.importlinter` — add the new module to the `layers` and `forbidden-imports` contracts
- `tests/test_environment_info.py` — tests for the `stdlib` field, `scope` subcommand, `resolve_scope`
- `tests/test_registrars.py` — add `LibrarySearchTools`, bump `EXPECTED_TOOL_COUNT` to 18
- `docs/architecture/architecture.md` — tool count, module overview, registrar count, probe subcommand list

## Steps

1. `step_1.md` — `probe.py`: `stdlib` info field + `scope` subcommand
2. `step_2.md` — `environment_info.py`: `EnvironmentInfo.stdlib` + `resolve_scope()`
3. `step_3.md` — `library_search.py`: directory search core (glob + content search)
4. `step_4.md` — `library_search.py`: `LibrarySearchTools` registrar, wires scope resolution + search core into the `search_library_files` MCP tool
5. `step_5.md` — wire into `server.py`, `tach.toml`, `.importlinter`, `test_registrars.py`, docs

Each step is one commit: failing test(s) first, then the minimal implementation, then
quality gates, then commit. Later steps depend on earlier ones having landed.
