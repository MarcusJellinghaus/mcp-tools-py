# Step 2 — Correct `README.md` "Available Tools"

**Context:** [summary.md](./summary.md) | Issue #224 | One commit.

Independent of Step 1; either order works.

## WHERE

Single file: `README.md`. No other file is touched in this step.

## WHAT

Thirteen edits. The README states its tool inventory in three places today — Overview
bullets (`:9-11`), Features (`:25-27`), Available Tools (`:416-433`) — all three saying
3 tools. After this step it states it in one place, as a 17-row table, and the other two
link to it. The remaining edits correct the parameter tables the Features section points
at, and the setup sections that name only pytest/pylint/mypy as the tools the configured
environment must contain.

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

### Edit 4a — Target Directory Auto-Detection (`:45-48`)

`resolve_target_directories` is imported by `pylint_tool`, `mypy_tool`, `ruff_check_tool`,
`ruff_fix_tool`, `bandit_tool`, `vulture_tool` and `formatter/formatter_tools.py` — the
three-tool list is the same drift as the rest of this step.

Find:
```
When `target_directories` is not specified, all checker tools (pylint, mypy, vulture)
auto-detect directories from `pyproject.toml`:
```
Replace:
```
When `target_directories` is not specified, the tools that accept it (pylint, mypy, ruff
check, ruff fix, bandit, vulture, and `run_format_code`) auto-detect directories from
`pyproject.toml`:
```

### Edit 4b — Pylint Parameters table (`:35-36`)

`run_pylint_check` also takes `max_issues` (`checker_tools/pylint_tool.py:23-26`); the
table omits it.

Find:
```
| `target_directories` | list | None (auto-detected) | Directories to analyze relative to project_dir. Auto-detected from `pyproject.toml` when omitted |
```
Replace:
```
| `target_directories` | list | None (auto-detected) | Directories to analyze relative to project_dir. Auto-detected from `pyproject.toml` when omitted |
| `max_issues` | integer | 1 | Number of issue types shown in detail; the rest are summarised as counts |
```

### Edit 4c — Pytest Parameters table (`:67-69`)

`run_pytest_check` takes only `markers`, `extra_args` and `env_vars`
(`checker_tools/pytest_tool.py:23-27`) — there is no `verbosity` parameter; verbosity is
controlled through `extra_args`.

Find:
```
| `markers` | list | None | Optional list of pytest markers to filter tests |
| `verbosity` | integer | 2 | Pytest verbosity level (0-3) |
| `extra_args` | list | None | Optional list of additional pytest arguments |
```
Replace:
```
| `markers` | list | None | Optional list of pytest markers to filter tests |
| `extra_args` | list | None | Optional list of additional pytest arguments; use `-v`/`-vv`/`-vvv` to control verbosity |
```

### Edit 4d — Mypy Parameters table (`:83`)

`run_mypy_check` also takes `cache_dir` (`checker_tools/mypy_tool.py:23-28`).

Find:
```
| `follow_imports` | string | 'normal' | How to handle imports during type checking |
```
Replace:
```
| `follow_imports` | string | 'normal' | How to handle imports during type checking |
| `cache_dir` | string | None (`.mypy_cache`) | Custom cache directory for incremental checking |
```

### Edit 4e — CLI Python Configuration table (`:104-105`)

Both rows name pytest, pylint and mypy only. `server.py:_check_tool_availability` also
looks for `lint-imports`, `vulture`, `ruff`, `bandit` and `tach` as binaries inside
`--venv-path`, and black and isort are invoked as `<python> -m black|isort`
(`formatter/black_runner.py:63`, `formatter/isort_runner.py:64`).

Find:
```
| `--python-executable` | string | sys.executable | Path to Python interpreter for running pytest, pylint, and mypy. Should point to the environment where these tools are installed (the tool's own venv), not the project's runtime venv |
| `--venv-path` | string | None | Path to the virtual environment where pytest, pylint, and mypy are installed. When specified, this venv's Python will be used instead of `--python-executable`. This should be the tool's own venv, not the project's runtime venv |
```
Replace:
```
| `--python-executable` | string | sys.executable | Path to the Python interpreter used to run pytest, pylint, mypy, black and isort. Should point to the environment where these tools are installed (the tool's own venv), not the project's runtime venv |
| `--venv-path` | string | None | Path to the virtual environment holding the checker tools. Required for the ones located as binaries: ruff, bandit, vulture, tach and lint-imports. When specified, this venv's Python will be used instead of `--python-executable`. This should be the tool's own venv, not the project's runtime venv |
```

### Edit 4f — Environment Configuration (`:129`)

Find:
```
The `--python-executable` and `--venv-path` options must point to the environment where **pytest, pylint, and mypy are installed** — this is typically the tool's own virtual environment, not your project's runtime venv.
```
Replace:
```
The `--python-executable` and `--venv-path` options must point to the environment where **the checker tools are installed** — pytest, pylint, mypy, black and isort are run through that interpreter, while ruff, bandit, vulture, tach and lint-imports are located as binaries inside `--venv-path`. This is typically the tool's own virtual environment, not your project's runtime venv.
```

### Edit 4g — Incorrect Configuration (`:151`)

Find:
```
Do **not** point to your project's runtime venv if it doesn't have pytest/pylint/mypy installed:
```
Replace:
```
Do **not** point to your project's runtime venv if it doesn't have the checker tools installed:
```

### Edit 4h — Troubleshooting (`:171`)

Find:
```
- **"No module named pytest"** (or pylint/mypy): Your `--python-executable` or `--venv-path` points to an environment that doesn't have the required tools installed. Update the configuration to point to the correct environment.
```
Replace:
```
- **"No module named pytest"** (or pylint/mypy/black/isort): Your `--python-executable` or `--venv-path` points to an environment that doesn't have the required tools installed. Update the configuration to point to the correct environment.
- **"ruff not found"** (or bandit/vulture/tach/lint-imports) logged at startup: these tools are located as binaries inside `--venv-path`. Set `--venv-path` to an environment where they are installed.
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
5. The three parameter tables match the tool signatures: `run_pylint_check`
   (`extra_args`, `target_directories`, `max_issues`), `run_pytest_check` (`markers`,
   `extra_args`, `env_vars` — no `verbosity`), `run_mypy_check` (`strict`,
   `disable_error_codes`, `target_directories`, `follow_imports`, `cache_dir`).
6. No occurrence of `pytest, pylint, and mypy` or `pytest/pylint/mypy installed` remains
   in `README.md`.
7. Run `mcp__mcp-tools-py__run_format_code`, then `run_pylint_check`,
   `run_pytest_check` (`extra_args: ["-n", "auto"]`) and `run_mypy_check`. All must pass.

## Commit

```
docs(readme): list all 17 MCP tools in one table

The README documented 3 of 17 tools, and did so in three separate
places that had each drifted. Replaces the per-tool prose with a single
table and points the Overview and Features sections at it, so a new
tool costs one row in one place. Also corrects the parameter tables
(no pytest `verbosity`, missing `max_issues` and `cache_dir`) and the
setup sections that named only pytest, pylint and mypy.

Refs #224
```
