# Step 1 — Correct `docs/architecture/architecture.md`

**Context:** [summary.md](./summary.md) | Issue #224 | One commit.

## WHERE

Single file: `docs/architecture/architecture.md`. No other file is touched in this step.

## WHAT

Thirteen edits across sections 1, 2, 3, 4, 5, 6 and the metadata header. Documentation only —
no functions, no signatures. Each edit below gives the exact current text and its
replacement; apply with `mcp__mcp-workspace__edit_file` exact-string matches.

## HOW

Line numbers are as of the branch point and shift as edits apply — match on text, not
position. Working top-down keeps earlier line numbers valid for orientation.

---

### Edit 1 — metadata (`:3`)

Find:
```
**Framework**: Arc42 Template | **Version**: 1.1 | **Last Updated**: 2026-03-23
```
Replace:
```
**Framework**: Arc42 Template | **Version**: 1.2 | **Last Updated**: 2026-09-01
```

### Edit 2 — §1 System Purpose (`:11`)

Find:
```
MCP server providing automated code quality checking (pylint, pytest, mypy) and Python refactoring tools (powered by jedi and rope) for Python projects, with LLM-optimized output designed for AI-assisted development workflows.
```
Replace:
```
MCP server providing automated code quality checking (pylint, pytest, mypy, ruff, bandit, vulture, tach, import-linter), code formatting (black, isort) and Python refactoring tools (powered by jedi and rope) for Python projects, with LLM-optimized output designed for AI-assisted development workflows.
```

### Edit 3 — §1 Scope (`:13`)

The "planned" claim is stale: vulture, tach and import-linter all ship.

Find:
```
**Scope:** This server covers Python projects only. Further Python-specific extensions are planned, including architecture and layering checks (vulture, tach, import-linter). Support for other languages can be provided through separate, dedicated MCP servers with similar functionality.
```
Replace:
```
**Scope:** This server covers Python projects only. Support for other languages can be provided through separate, dedicated MCP servers with similar functionality.
```

### Edit 4 — §1 Key Features (`:18-21`)

Find:
```
- **Pylint Integration**: Static analysis with configurable rules and LLM-friendly prompts
- **Pytest Integration**: Test execution with JSON report parsing, failure analysis, and smart detail control
- **Mypy Integration**: Static type checking with strict mode and configurable error codes
- **Refactoring Tools**: Symbol listing, reference finding, symbol/module moving, and renaming via jedi and rope
```
Replace:
```
- **Checker Integrations**: Eight checkers exposed as nine tools — pylint, pytest, mypy, ruff (check and fix), bandit, vulture, tach, import-linter — each formatting findings as an LLM-actionable prompt
- **Formatting**: black and isort behind a single `run_format_code` tool
- **Refactoring Tools**: Symbol listing, reference finding, symbol/module moving, and renaming via jedi and rope
- **Library Inspection**: `get_library_source` resolves a dotted import path to its source
```

### Edit 5 — §2 Dependencies (`:48-50`)

`ruff`, `bandit`, `vulture`, `tach`, `import-linter`, `black` and `isort` are in
`[project.dependencies]`, not the dev extra — the server shells out to them at runtime.

Find:
```
**Runtime**: `mcp`, `mcp[cli]`, `pylint`, `pytest` + `pytest-json-report` + `pytest-xdist`, `mypy`, `jedi`, `rope`, `structlog` + `python-json-logger`

**Development**: `mcp-coder`, `black` + `isort`, `import-linter` + `tach`, `pycycle`, `vulture`, `pydeps`
```
Replace:
```
**Runtime**: `mcp`, `mcp[cli]`, `pylint`, `pytest` + `pytest-json-report` + `pytest-asyncio` + `pytest-xdist`, `mypy`, `ruff`, `bandit`, `vulture`, `tach`, `import-linter`, `black`, `isort`, `jedi`, `rope`, `structlog` + `python-json-logger`, `pathspec`, `igittigitt`, `mcp-coder-utils`

**Development**: `mcp-workspace`, `pycycle`, `pydeps`
```

Before applying, confirm the dev extra contents against `[project.optional-dependencies]`
in `pyproject.toml` and adjust the Development line if it lists anything else.

### Edit 6 — §2 Formatting convention (`:58`)

`tools/format_all` does not exist in any extension. `.claude/CLAUDE.md` makes
`run_format_code` the mandatory pre-commit step; `tools/` has the two scripts separately.

`CONTRIBUTING.md` points at the same missing `tools\format_all.bat` in four places, and is
deliberately left alone here — see the exclusions in [summary.md](./summary.md#deliberate-scope-decisions).

Find:
```
- **Formatting**: Black + isort via `tools/format_all` before commits
```
Replace:
```
- **Formatting**: Black + isort via the `run_format_code` MCP tool before commits (`tools/black.bat` and `tools/iSort.bat` run them individually)
```

### Edit 7 — §3 Context diagram (`:64-88`)

Replace the whole fenced block, from the opening ``` through the closing ```, with:

````
```
┌─────────────────┐   STDIO/MCP   ┌──────────────────┐   subprocess    ┌─────────────────┐
│   MCP Client    │◄─────────────►│   mcp-tools-py   │────────────────►│ pylint  pytest  │
│                 │               │                  │                 │ mypy    ruff    │
│ • Claude Code   │               │  (MCP Server)    │                 │ bandit  vulture │
│ • Claude Desktop│               │  17 MCP tools:   │                 │ tach    black   │
│ • VSCode        │               │  9 checker +     │                 │ isort           │
│ • mcp-coder     │               │  1 formatter +   │                 │ lint-imports    │
│                 │               │  5 refactoring + │                 └─────────────────┘
│                 │               │  2 other         │   in-process    ┌─────────────────┐
└─────────────────┘               │                  │◄───────────────►│    jedi/rope    │
                                  └──────────────────┘                 │  (refactoring   │
                                           │                           │    library)     │
                                           ▼                           └─────────────────┘
                                   ┌──────────────┐
                                   │ Project Dir  │
                                   │ (target code │
                                   │  under test) │
                                   └──────────────┘
```
````

The "2 other" line covers `sleep` and `get_library_source`. The Data Flow list directly
below the diagram stays as it is — it is still accurate.

### Edit 7a — §4 Solution Strategy (`:99`)

The four-file structure is not universal — `vulture`, `tach` and `lint_imports` are
`runners.py` alone. Without this edit the line contradicts Edit 10 below.

Find:
```
- **Consistent Checker Pattern**: Each tool follows `models`/`parsers`/`reporting`/`runners` structure
```
Replace:
```
- **Consistent Checker Pattern**: Each checker package follows the same `models`/`parsers`/`reporting`/`runners` structure, using only the files its tool needs
```

### Edit 8 — §5 Layer diagram (`:115-135`)

Replace the whole fenced block with:

````
```
┌─────────────────────────────────────────────────────┐
│  Entry Point Layer                                  │
│  └── mcp_tools_py.main                              │
├─────────────────────────────────────────────────────┤
│  Server Layer                                       │
│  └── mcp_tools_py.server                            │
├─────────────────────────────────────────────────────┤
│  Tool Implementation Layer                          │
│  ├── Registrars: checker_tools, formatter,          │
│  │   refactoring, utility_tools, inspect_library    │
│  └── Checkers: code_checker_{pytest, pylint, mypy,  │
│      ruff, bandit, vulture, tach, lint_imports}     │
├─────────────────────────────────────────────────────┤
│  Utilities Layer                                    │
│  ├── mcp_tools_py.utils                             │
│  └── mcp_tools_py.log_utils                         │
└─────────────────────────────────────────────────────┘
```
````

All 13 `tool_implementation` modules in `tach.toml` are now represented. Layer count stays
at 4. Box width is 53 characters — keep the right-hand `│` aligned.

### Edit 9 — §5 Dependency Rules (`:137-140`)

Find:
```
- Each layer may only depend on layers below it
- Checker modules may NOT depend on each other
- `utils` may NOT depend on any checker module or `server`
```
Replace:
```
- Each layer may only depend on layers below it
- `checker_tools` depends on the `code_checker_*` packages, never the reverse; the other registrars (`formatter`, `refactoring`, `utility_tools`, `inspect_library`) depend on none of them
- Checker modules may NOT depend on each other
- `utils` may NOT depend on any checker module or `server`
```

### Edit 10 — §5 Checker Module Pattern (`:142-152`)

Find:
```
Each checker follows the same internal structure:
```
Replace:
```
Each checker is a package following the same internal structure. Files are present only
when the tool needs them — simple checkers (`vulture`, `tach`, `lint_imports`) are
`runners.py` alone.
```

Then, in the table below it, find:
```
| `utils.py` | Module-specific helpers (pytest and pylint only) |
```
Replace:
```
| `utils.py` | Module-specific helpers (optional; pytest and pylint only) |
```

Then append after the table, before the `### Module Overview` heading:
```
Each checker is exposed by one registrar module, `checker_tools/<tool>_tool.py`, holding a
single `register(mcp, checker_tools)` function. `checker_tools` was a single module until
#202 split it per tool.
```

### Edit 11 — §5 Module Overview (`:156-165`)

Replace the entire bullet list (from `- **`main.py`**` through
`- **`log_utils.py`**` inclusive) with:

```
- **`main.py`** — CLI entry point: argument parsing (`argparse`), logging setup, server creation
- **`server.py`** — `ToolServer`: creates the FastMCP instance and delegates registration to five registrars — `CheckerTools`, `FormatterTools`, `RefactoringTools`, `UtilityTools`, `InspectTools`. Exposes 17 tools total (9 checker + 1 formatter + 5 refactoring + 1 utility + 1 inspection)
- **`checker_tools/`** — `CheckerTools`: registers the 9 checker MCP tools, one `<tool>_tool.py` module each
- **`formatter/`** — `FormatterTools`: registers `run_format_code`; `black_runner.py` and `isort_runner.py` sequenced by `runner.py`
- **`refactoring/`** — `RefactoringTools`: registers 5 refactoring MCP tools (`list_symbols`, `find_references`, `move_symbol`, `rename_symbol`, `move_module`) powered by jedi and rope
- **`utility_tools.py`** — `UtilityTools`: registers `sleep`
- **`inspect_library.py`** — `InspectTools`: registers `get_library_source`, resolving a dotted import path to its source
- **`code_checker_*`** — eight checker packages, one per external tool (pytest, pylint, mypy, ruff, bandit, vulture, tach, lint_imports), each following the Checker Module Pattern above
- **`code_checker_pytest`** — the most complex of them: JSON report parsing, `OutputBuilder`, `show_details` logic, `ProcessResult` adapter
- **`utils/subprocess_runner.py`** — `execute_command()`, `CommandResult`, STDIO isolation for Python commands, cross-platform process termination
- **`utils/file_utils.py`** — `read_file()` with encoding fallback
- **`utils/project_config.py`** — target-directory auto-detection from `pyproject.toml`
- **`log_utils.py`** — `setup_logging()` (console/JSON file), `@log_function_call` decorator
```

Note the class rename in the `server.py` bullet: the current text says `CodeCheckerServer`,
but `src/mcp_tools_py/server.py` defines `ToolServer`.

### Edit 12 — §6 Runtime View (`:214`)

Find:
```
All three tools (pylint, pytest, mypy) follow this same pattern. The pylint and mypy paths are simpler (no JSON report parsing).
```
Replace:
```
All checker tools follow this same pattern. Only pytest parses a JSON report file; the others parse stdout directly.
```

---

## DATA

No data structures, return values or signatures change. The only artifact is the edited
Markdown file.

## Verification

TDD does not apply — no code changes. Verify instead:

1. Every module named in the new layer diagram exists in `tach.toml` under
   `layer = "tool_implementation"`, and every such module appears in the diagram.
   13 modules either way.
2. `tools/black.bat` and `tools/iSort.bat` exist, and `tools/format_all` (any extension)
   does not. `CONTRIBUTING.md` still references `tools\format_all.bat` — that is expected
   and out of scope, so do not assert a repo-wide absence.
3. No occurrence of `8 MCP tools`, `8 tools`, `3 checker`, `format_all`, or
   `CodeCheckerServer` remains in `docs/architecture/architecture.md`.
4. Run `mcp__mcp-tools-py__run_format_code`, then `run_pylint_check`,
   `run_pytest_check` (`extra_args: ["-n", "auto"]`) and `run_mypy_check`. All must pass —
   they should be untouched by a docs-only change; a failure means a source file was
   edited by mistake.

## Commit

```
docs(architecture): correct tool inventory and add missing packages

architecture.md described 8 tools from 6 packages; the server registers
17 from 13. Corrects the count in the context diagram and module
overview, adds the seven missing packages to the layer diagram and
overview, and retargets the formatting convention at the nonexistent
tools/format_all to run_format_code.

Refs #224
```
