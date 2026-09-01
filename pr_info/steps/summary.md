# Summary — Issue #224: docs describe 8 and 3 MCP tools; 17 exist

## Goal

`docs/architecture/architecture.md` and `README.md` describe a much smaller server than
the one that exists. Bring both in line with the 17 tools the server actually registers,
and remove the duplicated inventories that caused the drift.

## Verified current state

17 tools, counted from `@mcp.tool()` decorators, registered by five registrars in
`src/mcp_tools_py/server.py:83-89`:

| Registrar | Count | Tools |
|---|---|---|
| `CheckerTools` | 9 | `run_pylint_check`, `run_pytest_check`, `run_mypy_check`, `run_ruff_check`, `run_ruff_fix`, `run_bandit_check`, `run_vulture_check`, `run_tach_check`, `run_lint_imports_check` |
| `FormatterTools` | 1 | `run_format_code` |
| `RefactoringTools` | 5 | `list_symbols`, `find_references`, `move_symbol`, `rename_symbol`, `move_module` |
| `UtilityTools` | 1 | `sleep` |
| `InspectTools` | 1 | `get_library_source` |

## Scope

Documentation only. **No source, test, or config file is touched.** No behaviour changes.

## Testing note

TDD does not apply — there is no code under change. Each step instead carries an explicit
verification block. The full check suite still runs before each commit, to catch an
accidental source edit rather than to prove new behaviour.

## Architectural / design changes

No runtime architecture changes. The *documented* architecture changes as follows, and
these are the design decisions worth recording:

1. **Layer diagram splits the Tool Implementation layer into two named tiers**
   (Registrars / Checkers) instead of one flat list. This is the shape `.importlinter`
   already encodes as two adjacent layers, and it makes the registrar → checker
   dependency direction visible. The layer *count* stays at 4, matching `tach.toml` and
   `architecture-maintenance.md` §5.2 question 4.

2. **Modules are grouped, not enumerated per file.** The eight `code_checker_*` packages
   get one grouped bullet plus a note on `code_checker_pytest` (the only one that differs
   materially), rather than eight near-identical bullets. Same reasoning for the layer
   diagram, which uses brace notation rather than one line per package. A new checker
   costs an edit inside an existing line, not a new line.

3. **The Checker Module Pattern table stays a 5-row file table** and gains an
   "optional" qualifier plus one sentence naming the runners-only checkers
   (`vulture`, `tach`, `lint_imports`). A per-package × per-file matrix was rejected:
   it needs a new row per checker, which is the same drift the issue is reporting.

4. **The README states its tool inventory exactly once.** It currently states it in
   three places — Overview bullets, Features, Available Tools — all three saying 3 tools.
   Available Tools becomes the single source; Overview and Features link to it. This is
   fewer edits now than fixing three lists, and one place to touch per future tool.

5. **Available Tools becomes a two-column table, one row per tool.** The per-tool prose
   format cost a four-bullet block per new tool, which is why it drifted. No per-registrar
   subheadings — that would be five tables to keep aligned; grouping is conveyed by row
   order.

6. **No drift-guard test.** A test asserting the README table matches the registered tool
   names would need the registrars imported to enumerate names and would break on
   formatting changes. The reduced drift surface above is the proportionate fix.

## Files created or modified

**Modified (2):**

| Path | Step | Change |
|------|------|--------|
| `docs/architecture/architecture.md` | 1 | Sections 1, 2, 3, 4, 5, 6 + metadata |
| `README.md` | 2 | Overview, Scope, Security bullet, Features, Target Directory Auto-Detection, Available Tools |

**Created (planning artifacts only):**

- `pr_info/steps/summary.md`
- `pr_info/steps/step_1.md`
- `pr_info/steps/step_2.md`

**Explicitly not modified:** `src/**`, `tests/**`, `tach.toml`, `.importlinter`,
`pyproject.toml`, `CONTRIBUTING.md`, `docs/README.md`,
`docs/architecture/architecture-maintenance.md`,
`docs/architecture/dependencies/readme.md`.

## Steps

| Step | Deliverable | Commit |
|------|-------------|--------|
| [1](./step_1.md) | `docs/architecture/architecture.md` corrected | 1 |
| [2](./step_2.md) | `README.md` corrected | 1 |

The two steps are independent and may be done in either order.

## Deliberate scope decisions

**Included beyond the issue's five findings** — each of these still asserts "3 tools" or
"8 tools" after the main fix, so leaving them creates a self-contradicting document:

- `architecture.md:11` System Purpose (pylint/pytest/mypy only)
- `architecture.md:13` and `README.md:13` — call vulture/tach/import-linter "planned"; all three ship
- `architecture.md:17-23` Key Features — three checkers listed
- `architecture.md:48-50` Dependencies — `ruff`, `bandit`, `vulture`, `tach`, `black`, `isort`, `import-linter` are listed as Development but are in `[project.dependencies]`
- `architecture.md:99` "Each tool follows `models`/`parsers`/`reporting`/`runners` structure" — `vulture`, `tach` and `lint_imports` are `runners.py` alone
- `architecture.md:214` "All three tools (pylint, pytest, mypy) follow this same pattern"
- `README.md:47` — names pylint, mypy and vulture as the tools that auto-detect target directories; `resolve_target_directories` is also used by ruff check, ruff fix, bandit and `run_format_code`
- `architecture.md:157` names `CodeCheckerServer`; the class is `ToolServer`
- `README.md:9-11`, `:19`, `:25-27` — the other two tool inventories

**One per-file addition beyond the issue's seven packages:** `utils/project_config.py`.
The Module Overview lists `utils/` contents file-by-file, so omitting it leaves that list
wrong by omission, and it implements the target-directory auto-detection the README
documents.

**Excluded:**

- `architecture.md:263` — the CI "Always" list omits the `ruff-docstrings` and
  `file-size` matrix jobs. That is CI-config drift, not tool-inventory drift, and nothing
  in the corrected text contradicts it. Worth its own issue.
- `CONTRIBUTING.md` — references `tools\format_all.bat` at `:106`, `:224`, `:252` and
  `:274`, the same missing script as `architecture.md:58`. It also points at
  `tools\ruff_fix.bat`, `tools\git_status.bat` and `tools\test_cli_installation.bat`,
  none of which exist either. Fixing only the `format_all` lines would leave the
  neighbouring lines equally wrong, and fixing all of them is a CONTRIBUTING audit, not
  tool-inventory drift. Worth its own issue. Step 1's verification therefore checks
  `format_all` inside `architecture.md` only, not repo-wide.
