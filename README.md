# MCP Tools Py

A Model Context Protocol (MCP) server providing code quality checking operations with easy client configuration. This server offers an API for performing code quality checks within a specified project directory, following the MCP protocol design.

## Overview

This MCP server enables AI assistants like Claude (via Claude Desktop), VSCode with GitHub Copilot, or other MCP-compatible clients to run code quality checks, formatting and refactoring on Python projects. See [Available Tools](#available-tools) for the full list.

**Scope:** This server covers Python projects only. Support for other languages can be provided through separate, dedicated MCP servers with similar functionality.

**Why a dedicated MCP server instead of bash access?**

A general-purpose bash MCP tool allows more flexibility, but at the expense of less control. This server takes a more focused approach:

- **Security**: Only a defined set of tools can be executed — see [Available Tools](#available-tools). All operations are scoped to the specified `project_dir`.
- **Context management**: Results are formatted and size-limited to reduce context load on the AI assistant. Output is structured as actionable prompts rather than raw tool output.
- **Transparency**: The server is open source, and detailed structured logging records every tool call with parameters, timing, and results.

## Features

All tools are listed under [Available Tools](#available-tools). The sections below
document the parameters of the most-used ones.

### Pylint Parameters

The pylint tools expose the following parameters for customization:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `extra_args` | list | None | Optional list of additional pylint CLI arguments (e.g. `["--disable=W0611"]`) |
| `target_directories` | list | None (auto-detected) | Directories to analyze relative to project_dir. Auto-detected from `pyproject.toml` when omitted |
| `max_issues` | integer | 1 | Number of issue types shown in detail; the rest are summarised as counts |

### Pylint Configuration

Pylint reads your project's `pyproject.toml` automatically. Control which issues
are reported by configuring `[tool.pylint.messages_control]` in your `pyproject.toml`.
See [docs/pyproject-configuration.md](docs/pyproject-configuration.md) for examples
and migration guidance.

### Target Directory Auto-Detection

When `target_directories` is not specified, the tools that accept it (pylint, mypy, ruff
check, ruff fix, bandit, vulture, and `run_format_code`) auto-detect directories from
`pyproject.toml`:

- **Source dirs** from `[tool.setuptools.packages.find] where` (fallback: `["src"]`)
- **Test dirs** from `[tool.pytest.ini_options] testpaths` (fallback: `["tests"]`)

Only directories that exist on disk are included. You can override auto-detection
by passing an explicit list:

- `["src"]` - Analyze only source code directory
- `["src", "tests"]` - Analyze both source and test directories
- `["mypackage", "tests"]` - For projects with different package structures
- `["."]` - Analyze entire project directory (may be slow for large projects)

### Pytest Parameters

`run_pytest_check` exposes the following parameters for customization:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `markers` | list | None | Optional list of pytest markers to filter tests |
| `extra_args` | list | None | Optional list of additional pytest arguments; use `-v`/`-vv`/`-vvv` to control verbosity |
| `env_vars` | dictionary | None | Optional environment variables for the subprocess |

**Note:** Parallel test execution is enabled by default using pytest-xdist (`-n auto`).

### Mypy Parameters

The mypy tools expose the following parameters for customization:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `strict` | boolean | True | Use strict mode settings |
| `disable_error_codes` | list | None | List of mypy error codes to ignore |
| `target_directories` | list | None (auto-detected) | Directories to check relative to project_dir. Auto-detected from `pyproject.toml` when omitted |
| `follow_imports` | string | 'normal' | How to handle imports during type checking |
| `cache_dir` | string | None (`.mypy_cache`) | Custom cache directory for incremental checking |

## Command Line Interface (CLI)

### Basic Usage

```bash
mcp-tools-py --project-dir /path/to/project [options]
```

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `--project-dir` | string | **Required**. Base directory for code checking operations |

### Optional Parameters

#### Python Configuration
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--python-executable` | string | sys.executable | Path to the Python interpreter used to run pytest, pylint, mypy, black and isort. Should point to the environment where these tools are installed (the tool's own venv), not the project's runtime venv |
| `--venv-path` | string | None | Path to the virtual environment holding the checker tools. Required for the ones located as binaries: ruff, bandit, vulture, tach and lint-imports. When specified, this venv's Python will be used instead of `--python-executable`. This should be the tool's own venv, not the project's runtime venv |

#### Test Configuration
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--test-folder` | string | "tests" | Path to the test folder (relative to project-dir) |
| `--keep-temp-files` | flag | False | Keep temporary files after test execution. Useful for debugging when tests fail |

#### Logging Configuration
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `--log-level` | string | "INFO" | Set logging level. Choices: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `--log-file` | string | None | Path for structured JSON logs. If not specified, logs only to console |
| `--console-only` | flag | False | Log only to console, ignore `--log-file` parameter |

### Notes

- When `--venv-path` is specified, it takes precedence over `--python-executable`
- The `--console-only` flag is useful during development to avoid creating log files
- Log files are created in JSON format for structured analysis
- Temporary files are automatically cleaned up unless `--keep-temp-files` is specified

## Environment Configuration

The `--python-executable` and `--venv-path` options must point to the environment where **the checker tools are installed** — pytest, pylint, mypy, black and isort are run through that interpreter, while ruff, bandit, vulture, tach and lint-imports are located as binaries inside `--venv-path`. This is typically the tool's own virtual environment, not your project's runtime venv.

### Correct Configuration

Point to the venv where mcp-tools-py and its tools are installed:

```json
{
    "mcpServers": {
        "mcp-tools-py": {
            "command": "mcp-tools-py",
            "args": [
                "--project-dir", "/path/to/your/project",
                "--venv-path", "${VIRTUAL_ENV}"
            ]
        }
    }
}
```

### Incorrect Configuration

Do **not** point to your project's runtime venv if it doesn't have the checker tools installed:

```json
{
    "mcpServers": {
        "mcp-tools-py": {
            "command": "mcp-tools-py",
            "args": [
                "--project-dir", "/path/to/your/project",
                "--venv-path", "/path/to/your/project/.venv"
            ]
        }
    }
}
```

This will fail if your project's `.venv` doesn't have the required tools installed.

### Troubleshooting

- **"No module named pytest"** (or pylint/mypy/black/isort): Your `--python-executable` or `--venv-path` points to an environment that doesn't have the required tools installed. Update the configuration to point to the correct environment.
- **"ruff not found"** (or bandit/vulture/tach/lint-imports) logged at startup: these tools are located as binaries inside `--venv-path`. Set `--venv-path` to an environment where they are installed.
- **After installing missing tools**, restart the MCP server for changes to take effect. Tool availability is checked at startup and cached for the session.

## Installation

See [INSTALL.md](INSTALL.md) for detailed installation instructions.

**Quick install:**

```bash
# Install from GitHub (recommended)
pip install git+https://github.com/MarcusJellinghaus/mcp-tools-py.git

# Verify installation
mcp-tools-py --help
```

**Development install:**

```bash
# Clone and install for development
git clone https://github.com/MarcusJellinghaus/mcp-tools-py.git
cd mcp-tools-py
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"
mcp-tools-py --help
```

## MCP Client Configuration

This server can be configured with [mcp-config](https://github.com/MarcusJellinghaus/mcp-config), a separate Python tool you install yourself — it is not a dependency of this package. It provides:

- **Interactive setup**: Works with Claude Desktop and VSCode
- **Configuration management**: Add, remove, and view server configurations
- **Server repository**: Access to curated MCP server collection

**Prerequisites:** Install Python, then install mcp-config separately.

**Note:** While other MCP clients like Windsurf and Cursor support MCP servers, they may require manual configuration.

## Using as a Dependency

### In requirements.txt

Add this line to your `requirements.txt`:

```txt
mcp-tools-py @ git+https://github.com/MarcusJellinghaus/mcp-tools-py.git
```

### In pyproject.toml

Add to your project dependencies:

```toml
[project]
dependencies = [
    "mcp-tools-py @ git+https://github.com/MarcusJellinghaus/mcp-tools-py.git",
    # ... other dependencies
]

# Or as an optional dependency
[project.optional-dependencies]
dev = [
    "mcp-tools-py @ git+https://github.com/MarcusJellinghaus/mcp-tools-py.git",
]
```

### Installation Commands

After adding to requirements.txt or pyproject.toml:

```bash
# Install from requirements.txt
pip install -r requirements.txt

# Install from pyproject.toml
pip install .
# Or with optional dependencies
pip install ".[dev]"
```

## Running the Server

### Using the CLI Command (Recommended)
After installation, you can run the server using the `mcp-tools-py` command:

```bash
mcp-tools-py --project-dir /path/to/project [options]
```

### Using Python Module (Alternative)
You can also run the server as a Python module:

```bash
python -m mcp_tools_py --project-dir /path/to/project [options]

# Or for development (from source directory)
python -m src.main --project-dir /path/to/project [options]
```

For detailed information about all available command-line options, see the [CLI section](#command-line-interface-cli).

## Project Structure Support

The server automatically detects and analyzes Python code in standard project structures:

**Default Analysis:**
- `src/` directory (if present) - Main source code
- `tests/` directory (if present) - Test files

**Custom Project Structures:**
Use the `target_directories` parameter to specify different directories:

```python
# For a package-based structure
target_directories = ["mypackage", "tests"]

# For a simple project with code in root
target_directories = ["."]

# For complex multi-module projects
target_directories = ["module1", "module2", "shared", "tests"]
```

## Structured Logging

The server provides comprehensive logging capabilities:

- **Standard human-readable logs** to console for development/debugging
- **Structured JSON logs** to file for analysis and monitoring
- **Function call tracking** with parameters, timing, and results
- **Automatic error context capture** with full stack traces
- **Configurable log levels** (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Default timestamped log files** in `project_dir/logs/mcp_tools_py_{timestamp}.log`

Example structured log entries:
```json
{
  "timestamp": "2025-08-05 14:30:15",
  "level": "info",
  "event": "Starting pylint check",
  "project_dir": "/path/to/project",
  "disable_codes": ["C0114", "C0116"],
  "target_directories": ["src", "tests"]
}
```

Use `--console-only` to disable file logging for simple development scenarios.

## Quick MCP Client Setup

### Automated Setup (Recommended)

1. **First install the server:**
   ```bash
   pip install git+https://github.com/MarcusJellinghaus/mcp-tools-py.git
   ```

2. **Configure with [mcp-config](https://github.com/MarcusJellinghaus/mcp-config)** (install it separately — it is not pulled in by this package):
   ```bash
   mcp-config
   ```
   Then select "Add New" and search for this server.

This will prompt you for your project directory and automatically configure your MCP client.

**Note:** mcp-config's server registry does not yet carry an entry for `mcp-tools-py`, so use the Manual Setup below if it cannot find this server.

### Manual Setup

If you prefer manual configuration, edit your MCP configuration file:

**Claude Desktop** (`%APPDATA%\Claude\claude_desktop_config.json` on Windows):
```json
{
    "mcpServers": {
        "mcp-tools-py": {
            "command": "mcp-tools-py",
            "args": ["--project-dir", "/path/to/your/project"]
        }
    }
}
```

**For development mode:**
```json
{
    "mcpServers": {
        "mcp-tools-py": {
            "command": "python",
            "args": [
                "-m",
                "src.main",
                "--project-dir",
                "/path/to/your/project"
            ],
            "env": {
                "PYTHONPATH": "/path/to/mcp-tools-py"
            }
        }
    }
}
```

**VSCode** (`.vscode/mcp.json`):
```json
{
    "servers": {
        "mcp-tools-py": {
            "command": "mcp-tools-py",
            "args": ["--project-dir", "."]
        }
    }
}
```

**VSCode development mode:**
```json
{
    "servers": {
        "mcp-tools-py": {
            "command": "python",
            "args": ["-m", "src.main", "--project-dir", "."],
            "env": {
                "PYTHONPATH": "/path/to/mcp-tools-py"
            }
        }
    }
}
```



## Testing with MCP Inspector

```bash
npx @modelcontextprotocol/inspector mcp-tools-py --project-dir /path/to/project
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

## Development

### Setting up the development environment

```bash
# Clone the repository
git clone https://github.com/MarcusJellinghaus/mcp-tools-py.git
cd mcp-tools-py

# Create and activate a virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix/MacOS:
source .venv/bin/activate

# Install dependencies
pip install -e .

# Install development dependencies
pip install -e ".[dev]"
```

## Running with MCP Dev Tools

```bash
# Set the PYTHONPATH and run the server module using mcp dev
set PYTHONPATH=. && mcp dev src/server.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

The MIT License is a permissive license that allows reuse with minimal restrictions. It permits use, copying, modification, and distribution with proper attribution.

## Links

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Filesystem Tools](https://github.com/MarcusJellinghaus/mcp-workspace)
