# MCP Tools Py Architecture Documentation

**Framework**: Arc42 Template | **Version**: 1.0 | **Last Updated**: 2026-03-07
**Maintainer**: Marcus Jellinghaus | **Review Frequency**: On major changes

---

## 1. Introduction & Goals

### System Purpose
MCP server providing automated code quality checking (pylint, pytest, mypy) for Python projects, with LLM-optimized output designed for AI-assisted development workflows.

**Scope:** This server covers Python projects only. Further Python-specific extensions are planned, including architecture and layering checks (vulture, tach, import-linter) and refactoring tools. Support for other languages can be provided through separate, dedicated MCP servers with similar functionality.

Compared to a general-purpose bash MCP tool, this server offers a more controlled approach: only a defined set of tools can be executed, all operations are sandboxed within `project_dir`, output is size-limited to reduce context load, and behavior is transparent via open source code and detailed structured logging.

### Key Features
- **Pylint Integration**: Static analysis with configurable rules and LLM-friendly prompts
- **Pytest Integration**: Test execution with JSON report parsing, failure analysis, and smart detail control
- **Mypy Integration**: Static type checking with strict mode and configurable error codes
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
- **MCP Protocol** via STDIO transport, using `mcp[server]` (FastMCP)
- **Subprocess Execution**: All tools run as separate processes
- **JSON Report**: Pytest results via `pytest-json-report` plugin

### Dependencies

**Runtime**: `mcp[server,cli]`, `pylint`, `pytest` + `pytest-json-report` + `pytest-xdist`, `mypy`, `structlog` + `python-json-logger`, `mcp-config`

**Development**: `mcp-coder`, `black` + `isort`, `import-linter` + `tach`, `pycycle`, `vulture`, `pydeps`

See `pyproject.toml` for version constraints.

### Conventions
- **Quality Gates**: All three checks (pylint, pytest, mypy) must pass before proceeding
- **MCP Tool Usage**: No direct bash commands for code quality (documented in `.claude/CLAUDE.md`)
- **Architecture Enforcement**: `tach.toml` and `.importlinter` enforce module boundaries
- **Formatting**: Black + isort via `tools/format_all` before commits

---

## 3. Context & Scope

```
┌─────────────────┐    STDIO/MCP     ┌──────────────────┐    subprocess    ┌─────────────┐
│   MCP Client    │◄────────────────►│  mcp-tools-py │───────────────►│  pylint     │
│                 │                   │                   │               │  pytest     │
│ • Claude Code   │                   │  (MCP Server)     │               │  mypy       │
│ • Claude Desktop│                   │                   │               │             │
│ • VSCode        │                   │                   │               │ (subprocess │
│ • mcp-coder     │                   │                   │               │  execution) │
└─────────────────┘                   └──────────────────┘               └─────────────┘
                                              │
                                              ▼
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
- **Consistent Checker Pattern**: Each tool follows `models`/`parsers`/`reporting`/`runners` structure
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
│  Entry Point Layer                                   │
│  └── mcp_tools_py.main                          │
├─────────────────────────────────────────────────────┤
│  Server Layer                                        │
│  └── mcp_tools_py.server                        │
├─────────────────────────────────────────────────────┤
│  Checker Implementation Layer                        │
│  ├── mcp_tools_py.code_checker_pytest           │
│  ├── mcp_tools_py.code_checker_pylint           │
│  └── mcp_tools_py.code_checker_mypy             │
├─────────────────────────────────────────────────────┤
│  Utilities Layer                                     │
│  ├── mcp_tools_py.utils                         │
│  └── mcp_tools_py.log_utils                     │
└─────────────────────────────────────────────────────┘
```

**Dependency Rules** (enforced by `tach.toml` and `.importlinter`):
- Each layer may only depend on layers below it
- Checker modules may NOT depend on each other
- `utils` may NOT depend on any checker module or `server`

### Checker Module Pattern

Each checker follows the same internal structure:

| File | Responsibility |
|------|---------------|
| `models.py` | Data classes for tool output (e.g., `PylintMessage`, `PytestReport`) |
| `parsers.py` | Parse raw tool output into model objects |
| `reporting.py` | Format parsed results into LLM-optimized prompts |
| `runners.py` | Construct commands, execute subprocesses, orchestrate parse → report |
| `utils.py` | Module-specific helpers (pytest and pylint only) |

### Module Overview

- **`main.py`** — CLI entry point: argument parsing (`argparse`), logging setup, server creation
- **`server.py`** — `CodeCheckerServer`: MCP tool registration via FastMCP, 3 tools (`run_pylint_check`, `run_pytest_check`, `run_mypy_check`), result formatting
- **`code_checker_pytest`** — Most complex checker: JSON report parsing, `OutputBuilder`, `show_details` logic, `ProcessResult` adapter
- **`code_checker_pylint`** — Pylint JSON output parsing and prompt generation
- **`code_checker_mypy`** — Mypy text output parsing and prompt generation
- **`utils/subprocess_runner.py`** — `execute_command()`, `CommandResult`, STDIO isolation for Python commands, cross-platform process termination
- **`utils/file_utils.py`** — `read_file()` with encoding fallback
- **`log_utils.py`** — `setup_logging()` (console/JSON file), `@log_function_call` decorator

---

## 6. Runtime View

### Tool Invocation (e.g., `run_pytest_check`)

```
MCP Client          server.py              runners.py           subprocess_runner.py
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
    │                   │ _format_*_result()   │                        │
    │  formatted string │                      │                        │
    │◄──────────────────│                      │                        │
```

All three tools (pylint, pytest, mypy) follow this same pattern. The pylint and mypy paths are simpler (no JSON report parsing).

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
- Dual mode: console (human-readable) or JSON file (structured), configurable via CLI
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

### CI Pipeline

Matrix-based (`.github/workflows/ci.yml`, `fail-fast: false`):
- **Always**: black, isort, pylint (`-E`), pytest, mypy (strict)
- **PR only**: import-linter, tach, pycycle, vulture
