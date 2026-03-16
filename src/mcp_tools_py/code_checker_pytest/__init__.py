"""
Code checker package that runs pytest tests and analyzes the results.

This package provides functionality to run pytest tests on a given project
and process the test results.
"""

# Re-export public models individually
from mcp_tools_py.code_checker_pytest.models import (
    Collector,
    CollectorResult,
    Crash,
    Log,
    LogRecord,
    PytestReport,
    StageInfo,
    Summary,
    Test,
    TracebackEntry,
    Warning,
)
from mcp_tools_py.code_checker_pytest.parsers import parse_pytest_report
from mcp_tools_py.code_checker_pytest.reporting import (
    create_prompt_for_failed_tests,
    get_test_summary,
)

# Re-export runner functionality
# Re-export main functionality that should be part of the public API
from mcp_tools_py.code_checker_pytest.runners import (
    check_code_with_pytest,
    run_tests,
)

# Define the public API explicitly
__all__ = [
    # Models
    "Crash",
    "TracebackEntry",
    "LogRecord",
    "Log",
    "StageInfo",
    "Test",
    "CollectorResult",
    "Collector",
    "Summary",
    "Warning",
    "PytestReport",
    # Main functionality
    "run_tests",
    "parse_pytest_report",
    "check_code_with_pytest",
    "create_prompt_for_failed_tests",
    "get_test_summary",
]
