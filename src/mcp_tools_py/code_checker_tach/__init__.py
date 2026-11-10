"""Code checker package for running tach architecture boundary checks."""

from mcp_tools_py.code_checker_tach.parsers import TachDiagnostic, parse_tach_json
from mcp_tools_py.code_checker_tach.reporting import format_tach_report
from mcp_tools_py.code_checker_tach.runners import TachResult, run_tach_check

__all__ = [
    "TachDiagnostic",
    "TachResult",
    "format_tach_report",
    "parse_tach_json",
    "run_tach_check",
]
