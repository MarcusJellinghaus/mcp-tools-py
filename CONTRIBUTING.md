# Contributing to MCP Tools Py

Thank you for your interest in contributing to MCP Tools Py! This document provides guidelines and information for developers who want to contribute to the project.

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Development Workflow](#development-workflow)
- [Code Quality Standards](#code-quality-standards)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Submitting Changes](#submitting-changes)
- [Development Tools](#development-tools)

## Development Environment Setup

### Prerequisites

- Python 3.11 or higher
- git
- A code editor (VSCode recommended for optimal development experience)

### Initial Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/your-username/mcp-tools-py.git
   cd mcp-tools-py
   ```

2. **Create and activate virtual environment:**
   ```bash
   python -m venv .venv
   
   # On Windows:
   .venv\Scripts\activate
   
   # On Unix/macOS:
   source .venv/bin/activate
   ```

3. **Install development dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Verify installation:**
   ```bash
   mcp-tools-py --help
   pytest --version
   ```

## Development Workflow

### Daily Development Process

**For regular code changes (functions, bug fixes, features):**

1. Make your code changes
2. Test your changes (no reinstall needed)
3. Run quality checks before committing

**When you need to reinstall (entry points, dependencies, metadata changes):**

1. Run the reinstall script:
   ```bash
   call tools\reinstall_local.bat
   ```

2. This is needed when you modify:
   - Entry points in `pyproject.toml`
   - Dependencies in `pyproject.toml`
   - Package metadata

### Quality Assurance Process

After completing changes, **always** run the complete quality check pipeline:

1. **Run pylint checks:**
   ```bash
   tools\pylint_check_for_errors.bat
   ```

2. **Run pytest checks:**
   ```bash
   pytest tests/
   ```

3. **Run mypy checks:**
   ```bash
   tools\mypy.bat
   ```

**Alternative: Use the integrated checker script:**
```bash
tools\checks2clipboard.bat
```
This runs all checks in sequence and copies any issues to clipboard for easy analysis.

### Code Formatting

Format your code before committing:

```bash
# Format all code
tools\format_all.bat

# Or individually:
tools\ruff_fix.bat    # Fix common issues
tools\black.bat       # Code formatting
tools\iSort.bat       # Import sorting
```

## Code Quality Standards

### Python Guidelines

We use **Python 3.11+** with modern type hints:

- ✅ Use `dict, list, |` instead of `from typing import Dict, List, Union`
- ✅ Provide type hints for all functions (mypy strict compliance)
- ✅ Follow DRY principle - keep code concise
- ✅ Use absolute imports
- ✅ Use 4 spaces for indentation
- ✅ Only catch exceptions when truly required
- ✅ Focus on functionality - don't hide unexpected exceptions

### Documentation Standards

- **Google-style docstrings** for all public functions
- No docstrings needed for internal functions and unit tests
- Logging.debug statements don't need documentation

### Project Structure

```
mcp-tools-py/
├── src/                          # Main source code
│   ├── main.py                   # Entry point
│   ├── server.py                 # MCP server implementation
│   ├── code_checker_pylint/     # Pylint functionality
│   ├── code_checker_pytest/     # Pytest functionality
│   ├── code_checker_mypy/       # Mypy functionality
│   └── utils/                    # Shared utilities
├── tests/                        # Test files
│   ├── test_*.py                 # Unit tests
│   └── testdata/                 # Test data organized by test file
│       └── test_[name]/          # Test data for specific test file
├── tools/                        # Development scripts
└── PR_Info/                      # Explanatory documents for PRs
```

### Test Data Organization

Create test data in: `tests/testdata/[name of the python test file]/`

Example:
- Test file: `tests/test_server.py`
- Test data: `tests/testdata/test_server/sample_config.json`

## Testing

### Testing Framework

We use **pytest** for testing with specific guidelines:

- Test functionality, not logging output (avoid `caplog`)
- Unit tests must be independent and repeatable
- Clean up side effects after each test
- Import code from `src` folder

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_server.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=src
```

### Test Categories

Tests are organized with markers:

```bash
# CLI-specific tests
pytest -m cli

# Installation tests
pytest -m installation
```

## Submitting Changes

### Before Submitting

1. **Run the complete quality pipeline:**
   ```bash
   # Method 1: Use integrated script
   tools\checks2clipboard.bat
   
   # Method 2: Run individually
   # Step 1: Pylint
   python -m pylint src tests --fail-under=9.0
   
   # Step 2: Pytest  
   pytest tests/
   
   # Step 3: Mypy
   python -m mypy --strict src tests
   ```

2. **All checks must pass** before submitting PR

3. **Format code:**
   ```bash
   tools\format_all.bat
   ```

### Pull Request Guidelines

1. **Create descriptive commit messages**
2. **Reference issues** when applicable
3. **Include test coverage** for new features
4. **Update documentation** if needed
5. **Keep PRs focused** - one feature/fix per PR

### PR Review Process

When submitting PRs, the automated CI will run:
- Pylint checks (must pass)
- Full test suite (must pass)
- Mypy type checking (must pass)
- Code formatting validation

## Development Tools

The `tools/` directory contains helpful scripts for development:

### Code Quality Tools

- `checks2clipboard.bat` - Run all checks and copy results to clipboard
- `pylint_check_for_errors.bat` - Run pylint with error-level checking
- `mypy.bat` - Run mypy type checking
- `format_all.bat` - Format all code (runs ruff, black, isort)

### Development Utilities

- `reinstall_local.bat` - Reinstall package in development mode (uses local .venv)
- `git_status.bat` - Check git status
- `commit_summary.bat` - Generate commit summaries
- `pr_review.bat` - Generate PR review information

### Testing Tools

- `test_cli_installation.bat` - Test CLI command installation

### Using Development Tools

All tools should be run from the project root:

```bash
# Check code quality
tools\checks2clipboard.bat

# Format code
tools\format_all.bat

# Reinstall after pyproject.toml changes
call tools\reinstall_local.bat

# Check git status
tools\git_status.bat
```

## Advanced Development

### MCP Inspector Testing

Test your changes with MCP Inspector:

```bash
# For development mode
npx @modelcontextprotocol/inspector python -m src.main --project-dir .

# For installed package
npx @modelcontextprotocol/inspector mcp-tools-py --project-dir .
```

### VSCode Integration Testing

See `tests/manual_vscode_testing.md` for comprehensive VSCode integration testing procedures.

### Logging and Debugging

- Use `--log-level DEBUG` for detailed logging
- Log files are created in `project_dir/logs/` by default
- Use `--console-only` to disable file logging during development
- Use `--keep-temp-files` to inspect temporary files when debugging test failures

## Getting Help

- **Issues**: Create GitHub issues for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check README.md and INSTALL.md first
- **CI Failures**: Check the logs and run the same commands locally

## Important Notes

⚠️ **Code Changes and Restarts**: When code gets changed or edited, the current LLM session cannot use the updated code immediately. A new start is required. Make sure to inform users about this.

🔧 **MCP Server Logs**: The MCP server creates log files. When functionality isn't working as expected, always ask users for log files to analyze problems in detail.

📁 **PR Documentation**: While analyzing problems and doing fixes, you might create explanatory documents. Store them in the `PR_Info/` folder - these are useful for the PR but can be removed afterward.

---

**Happy Contributing!** Your contributions help make MCP Tools Py better for everyone.
