# MCP Tools Py Architecture Documentation

**Framework**: Arc42 Template | **Version**: 1.2 | **Last Updated**: 2026-09-01
**Maintainer**: Marcus Jellinghaus | **Review Frequency**: On major changes

---

## 1. Introduction & Goals

### System Purpose
MCP server providing automated code quality checking (pylint, pytest, mypy, ruff, bandit, vulture, tach, import-linter), code formatting (black, isort) and Python refactoring tools (powered by jedi and rope) for Python projects, with LLM-optimized output designed for AI-assisted development workflows.

**Scope:** This server covers Python projects only. Support for other languages can be provided through separate, dedicated MCP servers with similar functionality.

Compared to a general-purpose bash MCP tool, this server offers a more controlled approach: only a defined set of tools can be executed, all operations are sandboxed within `project_dir`, output is size-limited to reduce context load, and behavior is transparent via open source code and detailed structured logging.

### Key Features
- **Checker Integrations**: Eight checkers exposed as nine tools — pylint, pytest, mypy, ruff (check and fix), bandit, vulture, tach, import-linter — each formatting findings as an LLM-actionable prompt
- **Formatting**: black and isort behind a single `run_format_code` tool
- **Refactoring Tools**: Symbol listing, reference finding, symbol/module moving, and renaming via jedi and rope
- **Library Inspection**: `get_library_source` resolves a dotted import path to its source
- **LLM-Optimized Output**: Results formatted as actionable prompts for AI assistants
- **Subprocess Isolation**: STDIO isolation preventing MCP transport conflicts with Python subprocesses

### Quality Goals
- **Reliability**: Robust subprocess execution with timeout handling and error recovery
- **LLM Usability**: Output optimized for AI assistant comprehension and action
- **Cross-Platform**: Windows and Unix support with platform-specific process management
- **Extensibility**: Consistent checker module pattern enabling new tool integrations

### Stakeholders
- **AI Assistants**: Primary consumers — Claude Code, Claude Desktop, VSCode
- **Developers**: Configure and deploy the MCP server for their projects
- **MCP Coder**: Orchestration tool that uses this server for automated quality gates

---

## 2. Architecture Constraints

### Technical Constraints
- **Python 3.11+** minimum version
- **MCP Protocol** via STDIO transport, using `mcp` (FastMCP)
- **Subprocess Execution**: All tools run as separate processes
- **JSON Report**: Pytest results via `pytest-json-report` plugin

### Dependencies

**Runtime**: `mcp`, `mcp[cli]`, `pylint`, `pytest` + `pytest-json-report` + `pytest-asyncio` + `pytest-xdist`, `mypy`, `ruff`, `bandit`, `vulture`, `tach`, `import-linter`, `black`, `isort`, `jedi`, `rope`, `structlog` + `python-json-logger`, `pathspec`, `igittigitt`, `mcp-coder-utils`

**Development**: `mcp-workspace`, `pycycle`, `pydeps`

See `pyproject.toml` for version constraints.

### Conventions
- **Quality Gates**: All three checks (pylint, pytest, mypy) must pass before proceeding
- **MCP Tool Usage**: No direct bash commands for code quality (documented in `.claude/CLAUDE.md`)
- **Architecture Enforcement**: `tach.toml` and `.importlinter` enforce module boundaries
- **Formatting**: Black + isort via the `run_format_code` MCP tool before commits (`tools/black.bat` and `tools/iSort.bat` run them individually)

---

## 3. Context & Scope

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

### Data Flow
1. MCP Client → Server: Tool invocation with parameters
2. Server → Subprocess: Command construction with STDIO isolation
3. Subprocess → Server: Raw output (stdout/stderr) and JSON reports
4. Server → Parsers → Reporting: Parsed into models, formatted into LLM prompts
5. Server → MCP Client: Formatted result string

---

## 4. Solution Strategy

### Key Strategies
- **Layered Architecture**: Strict dependency direction enforced by tach and import-linter
- **Consistent Checker Pattern**: Each checker package follows the same `models`/`parsers`/`reporting`/`runners` structure, using only the files its tool needs
- **Subprocess Isolation**: File-based STDIO redirection to prevent MCP transport conflicts
- **LLM Prompt Generation**: Results transformed into actionable prompts, not raw output

### Architecture Patterns
- **Module Pattern**: Each checker is a self-contained package
- **Adapter Pattern**: `ProcessResult` bridges `CommandResult` to `subprocess.CompletedProcess`
- **Builder Pattern**: `OutputBuilder` manages line-counted, truncatable output
- **Decorator Pattern**: `@log_function_call` for function call logging with timing

---

## 5. Building Block View

### Layer Architecture

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

**Dependency Rules** (enforced by `tach.toml` and `.importlinter`):
- Each layer may only depend on layers below it
- `checker_tools` depends on the `code_checker_*` packages, never the reverse; the other registrars (`formatter`, `refactoring`, `utility_tools`, `inspect_library`) depend on none of them
- Checker modules may NOT depend on each other
- `utils` may NOT depend on anything above it: the `code_checker_*` packages, the registrars (`checker_tools`, `formatter`, `refactoring`, `utility_tools`, `inspect_library`) or `server`
- `mcp_coder_utils` may only be imported by the three shim modules — `log_utils`, `utils/file_utils.py` and `utils/subprocess_runner.py`; every other module imports it through them (`mcp_coder_utils_isolation` contract in `.importlinter`)

### Checker Module Pattern

Each checker is a package following the same internal structure. Files are present only
when the tool needs them — simple checkers (`vulture`, `tach`, `lint_imports`) are
`runners.py` alone.

| File | Responsibility |
|------|---------------|
| `models.py` | Data classes for tool output (e.g., `PylintMessage`, `PytestReport`) |
| `parsers.py` | Parse raw tool output into model objects |
| `reporting.py` | Format parsed results into LLM-optimized prompts |
| `runners.py` | Construct commands, execute subprocesses, orchestrate parse → report |
| `utils.py` | Module-specific helpers (optional; pytest and pylint only) |

Checkers are exposed by registrar modules, `checker_tools/<tool>_tool.py`, each holding a
single `register(mcp, checker_tools)` function. The eight checker packages have nine
registrar modules: `code_checker_ruff` backs two of them, `ruff_check_tool.py` and
`ruff_fix_tool.py`. `checker_tools` was a single module until #202 split it per tool.

### Module Overview

- **`main.py`** — CLI entry point: argument parsing (`argparse`), logging setup, server creation
- **`server.py`** — `ToolServer`: creates the FastMCP instance and delegates registration to five registrars — `CheckerTools`, `FormatterTools`, `RefactoringTools`, `UtilityTools`, `InspectTools`. Exposes 17 tools total (9 checker + 1 formatter + 5 refactoring + 1 utility + 1 inspection)
- **`checker_tools/`** — `CheckerTools`: registers the 9 checker MCP tools, one `<tool>_tool.py` module each
- **`formatter/`** — `FormatterTools`: registers `run_format_code`; `black_runner.py` and `isort_runner.py` sequenced by `runner.py`
- **`refactoring/`** — `RefactoringTools`: registers 5 refactoring MCP tools (`list_symbols`, `find_references`, `move_symbol`, `rename_symbol`, `move_module`) powered by jedi and rope
- **`utility_tools.py`** — `UtilityTools`: registers `sleep`
- **`inspect_library.py`** — `InspectTools`: registers `get_library_source`, resolving a dotted import path to its source
- **`code_checker_*`** — eight checker packages, one per external tool (pytest, pylint, mypy, ruff, bandit, vulture, tach, lint_imports), each following the Checker Module Pattern above
- **`code_checker_pytest`** — the most complex of them: JSON report parsing, `OutputBuilder`, `show_details` logic, `ProcessResult` adapter
- **`utils/subprocess_runner.py`** — thin re-export shim over `mcp_coder_utils.subprocess_runner`: `execute_command()`, `CommandResult`, STDIO isolation for Python commands, cross-platform process termination
- **`utils/file_utils.py`** — thin re-export shim over `mcp_coder_utils.fs`: `read_file()` with encoding fallback
- **`utils/project_config.py`** — target-directory auto-detection from `pyproject.toml`
- **`log_utils.py`** — thin re-export shim over `mcp_coder_utils.log_utils`: `setup_logging()` (console/JSON file), `@log_function_call` decorator

---

## 6. Runtime View

### Tool Invocation (e.g., `run_pytest_check`)

```
MCP Client       pytest_tool.py            runners.py           subprocess_runner.py
    │                   │                      │                        │
    │  run_pytest_check │                      │                        │
    │──────────────────►│                      │                        │
    │                   │  check_code_with_    │                        │
    │                   │  pytest()            │                        │
    │                   │─────────────────────►│                        │
    │                   │                      │  execute_command()     │
    │                   │                      │───────────────────────►│
    │                   │                      │                        │ [STDIO isolation]
    │                   │                      │   CommandResult        │
    │                   │                      │◄───────────────────────│
    │                   │                      │ parse + format         │
    │                   │  result dict         │                        │
    │                   │◄─────────────────────│                        │
    │                   │ CheckerTools._format_│                        │
    │                   │ pytest_result_with_  │                        │
    │                   │ details()            │                        │
    │  formatted string │                      │                        │
    │◄──────────────────│                      │                        │
```

All checker tools follow this same pattern, each entered through its own registrar module (`checker_tools/<tool>_tool.py`). Only pylint, pytest and mypy use the shared result formatters on `CheckerTools`; the other six format through their own package's reporting (for example `bandit_tool.py` calls `format_bandit_report`). Pytest and bandit write a JSON report to a temporary file and parse that; the other checkers parse stdout directly.

### STDIO Isolation (Python Subprocess)

When a Python command is detected (`is_python_command()`):
1. MCP-specific environment variables removed to prevent transport conflicts
2. Stdout/stderr redirected to temporary files instead of pipes
3. Process runs with `start_new_session=True` (Unix) for clean termination
4. Output read from files after completion; temp files cleaned up

---

## 7. Deployment View

See [README.md](../../README.md) for installation, CLI parameters, and MCP client configuration (Claude Desktop, VSCode, Claude Code).

- Installed via `pip install` (end user) or `pip install -e ".[dev]"` (development)
- Runs as STDIO-based MCP server, launched by the MCP client
- Requires `--project-dir` pointing to the target codebase
- Optional: `--venv-path` to use a specific virtual environment for tool execution

---

## 8. Cross-cutting Concepts

### Logging
- All modules use stdlib `logging.getLogger(__name__)` exclusively
- Structured fields passed via `extra={}` dict on stdlib log calls
- `log_utils.py` configures structlog internally for JSON file logging pipeline
- `@log_function_call` decorator captures parameters, timing, and results
- Default log location: `{project_dir}/logs/mcp_tools_py_{timestamp}.log`

### Architecture Enforcement

See [dependencies/readme.md](dependencies/readme.md) for tool comparison, current contracts, and update guidelines.

| Tool | Config | Purpose |
|------|--------|---------|
| tach | `tach.toml` | Layer boundary enforcement |
| import-linter | `.importlinter` | Import contract validation |
| pycycle | — | Circular dependency detection |
| vulture | `vulture_whitelist.py` | Dead code detection |

`.importlinter` holds three contracts: the layer contract, a forbidden-imports contract keeping `utils` free of imports from the `code_checker_*` packages, the registrars (`checker_tools`, `formatter`, `refactoring`, `utility_tools`, `inspect_library`) and `server`, and `mcp_coder_utils_isolation`, which confines `mcp_coder_utils` imports to the three shim modules.

### CI Pipeline

Matrix-based (`.github/workflows/ci.yml`, `fail-fast: false`):
- **Always**: black, isort, pylint (`-E`), pytest, mypy (strict)
- **PR only**: import-linter, tach, pycycle, vulture
