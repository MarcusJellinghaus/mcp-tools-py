# Vulture whitelist for mcp-tools-py
# This file contains identifiers that vulture should not report as dead code

# MCP server entry points and handlers
_.list_resources  # MCP server method
_.get_resource    # MCP server method
_.call_tool       # MCP server method

# FastMCP decorators and handlers
_.run_pytest_check     # FastMCP tool handler
_.run_pylint_check     # FastMCP tool handler  
_.run_mypy_check       # FastMCP tool handler
_.run_lint_imports_check  # FastMCP tool handler
_.run_vulture_check    # FastMCP tool handler
_.run_bandit_check     # FastMCP tool handler
# CLI entry points
_.main  # Entry point function

# Test fixtures and pytest hooks
_.pytest_configure
_.pytest_collection_modifyitems
_.pytest_runtest_setup

# Configuration and data model fields that may appear unused
_.project_dir
_.python_executable
_.venv_path
_.test_folder
_.log_level

# Exception classes that may not be directly instantiated
_Error
_Exception

# Model fields that may be accessed dynamically
_.dict
_.json
_.model_dump
_.model_validate

# LogRecord fields used by pytest JSON parsing - appear unused but needed for parsing
_.exc_info
_.exc_text
_.stack_info
_.msecs
_.relativeCreated
_.thread
_.threadName
_.processName
_.taskName
_.asctime

# Test model fields that may be parsed from JSON
_.teardown
_.when
_.category

# Utility functions that may be used conditionally
_.get_detailed_test_summary  # Used conditionally in reporting

# Test fixtures and mocks that appear unused
_.mock_pytest_results_success  # Test fixture
_.side_effect  # Mock attribute used in tests

# Data file variables used for module resolution
_.module_file_absolute

# MCP tool handler for library introspection
_.get_library_source  # FastMCP tool handler

# MCP tool handler for code formatting
_.run_format_code  # FastMCP tool handler

# Test mock attributes used for nested attribute resolution
_.b  # Mock attribute in test_inspect_library
_.c  # Mock attribute in test_inspect_library