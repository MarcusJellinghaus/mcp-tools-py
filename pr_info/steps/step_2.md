# Step 2 — Correct `README.md` "Available Tools"

**Context:** [summary.md](./summary.md) | Issue #224 | One commit.

Independent of Step 1; either order works.

## WHERE

Single file: `README.md`. No other file is touched in this step.

## WHAT

Five edits. The README states its tool inventory in three places today — Overview bullets
(`:9-11`), Features (`:25-27`), Available Tools (`:416-433`) — all three saying 3 tools.
After this step it states it in one place, as a 17-row table, and the other two link to it.

## HOW

Exact-string edits via `mcp__mcp-workspace__edit_file`. Match on text, not line number.

---

### Edit 1 — Overview (`:7-11`)

Find:
```
This MCP server enables AI assistants like Claude (via Claude Desktop), VSCode with GitHub Copilot, or other MCP-compatible clients to run code quality checks on Python projects. The tools provided are:

- Run pylint checks to identify code quality issues
- Execute pytest to identify failing tests
- Run mypy for type checking
```
Replace:
```
This MCP server enables AI assistants like Claude (via Claude Desktop), VSCode with GitHub Copilot, or other MCP-compatible clients to run code quality checks, formatting and refactoring on Python projects. See [Available Tools](#available-tools) for the full list.
```

### Edit 2 — Scope (`:13`)

vulture, tach and import-linter ship; refactoring tools ship.

Find:
```
**Scope:** This server covers Python projects only. Further Python-specific extensions are planned, including architecture and layering checks (vulture, tach, import-linter) and refactoring tools. Support for other languages can be provided through separate, dedicated MCP servers with similar functionality.
```
Replace:
```
**Scope:** This server covers Python projects only. Support for other languages can be provided through separate, dedicated MCP servers with similar functionality.
```

### Edit 3 — Security bullet (`:19`)

Find:
```
- **Security**: Only a defined set of tools (pylint, pytest, mypy) can be executed. All operations are scoped to the specified `project_dir`.
```
Replace:
```
- **Security**: Only a defined set of tools can be executed — see [Available Tools](#available-tools). All operations are scoped to the specified `project_dir`.
```

### Edit 4 — Features (`:23-27`)

Keep the `## Features` heading: the `### Pylint Parameters` / `### Pytest Parameters` /
`### Mypy Parameters` subsections nest under it and must stay nested.

Find:
```
## Features

- `run_pylint_check`: Run pylint on the project code and generate smart prompts for LLMs
- `run_pytest_check`: Run pytest on the project code and generate smart prompts for LLMs
- `run_mypy_check`: Run mypy type checking on the project code
```
Replace:
```
## Features

All tools are listed under [Available Tools](#available-tools). The sections below
document the parameters of the most-used ones.
```

### Edit 5 — Available Tools (`:412-433`)

Replace the section from the `## Available Tools` heading through the end of the
`### Run Mypy Check` bullet list (the line ending `...and target directories`),
stopping before `## Development`, with:

```
## Available Tools

The server exposes 17 MCP tools.

| Tool | What it does |
|------|--------------|
| `run_pylint_check` | Static analysis; findings returned as an LLM-actionable prompt |
| `run_pytest_check` | Runs the test suite, parses the JSON report, summarises failures |
| `run_mypy_check` | Strict-mode type checking with configurable error codes |
| `run_ruff_check` | Ruff lint analysis, read-only |
| `run_ruff_fix` | Applies ruff's safe fixes in place; unsafe fixes are opt-in |
| `run_bandit_check` | Security lint |
| `run_vulture_check` | Dead-code detection against `vulture_whitelist.py` |
| `run_tach_check` | Architectural boundary validation from `tach.toml` |
| `run_lint_imports_check` | Import-contract validation from `.importlinter` |
| `run_format_code` | Runs isort then black; `check_only` reports without writing |
| `list_symbols` | Top-level functions, classes and variables in a file |
| `find_references` | All references to a symbol across the project |
| `move_symbol` | Moves top-level symbols to another module, updating imports |
| `rename_symbol` | Renames a module-level symbol project-wide |
| `move_module` | Moves a module into another package, updating references |
| `get_library_source` | Resolves a dotted import path and returns its source |
| `sleep` | Pauses execution for a given number of seconds |

Parameters for pylint, pytest and mypy are documented under [Features](#features).
```

Row order is checkers → formatter → refactoring → inspection → utility. No per-registrar
subheadings: that would be five separate tables to keep aligned, and the grouping reads
from the ordering.

---

## DATA

No data structures, return values or signatures change. The only artifact is the edited
Markdown file.

## Verification

TDD does not apply — no code changes. Verify instead:

1. The table has exactly 17 rows, and every tool name in it matches a tool registered in
   `src/mcp_tools_py/`. Cross-check against the table in
   [summary.md](./summary.md#verified-current-state).
2. Both `#available-tools` anchors and the `#features` anchor resolve — the
   `## Available Tools` and `## Features` headings must remain unchanged in wording.
3. The `### Pylint Parameters`, `### Pytest Parameters` and `### Mypy Parameters`
   subsections are still present and still nested under `## Features`.
4. No occurrence of `(pylint, pytest, mypy) can be executed` or the three
   `### Run … Check` prose blocks remains.
5. Run `mcp__mcp-tools-py__run_format_code`, then `run_pylint_check`,
   `run_pytest_check` (`extra_args: ["-n", "auto"]`) and `run_mypy_check`. All must pass.

## Commit

```
docs(readme): list all 17 MCP tools in one table

The README documented 3 of 17 tools, and did so in three separate
places that had each drifted. Replaces the per-tool prose with a single
table and points the Overview and Features sections at it, so a new
tool costs one row in one place.

Refs #224
```
