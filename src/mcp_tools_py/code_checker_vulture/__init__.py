"""Code checker package for running vulture dead-code analysis."""

from mcp_tools_py.code_checker_vulture.reporting import format_vulture_report
from mcp_tools_py.code_checker_vulture.runners import VultureResult, run_vulture_check

__all__ = ["run_vulture_check", "VultureResult", "format_vulture_report"]
