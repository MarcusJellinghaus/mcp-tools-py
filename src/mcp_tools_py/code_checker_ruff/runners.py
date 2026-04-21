"""Functions for running ruff check and ruff fix."""

import logging
import os

from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.subprocess_runner import execute_command

from mcp_tools_py.code_checker_ruff.parsers import parse_ruff_json_output
from mcp_tools_py.code_checker_ruff.reporting import (
    format_ruff_check_report,
    format_ruff_fix_report,
)

logger = logging.getLogger(__name__)


def _build_ruff_command(
    ruff_binary: str,
    target_directories: list[str],
    select: list[str] | None = None,
    extra_args: list[str] | None = None,
    output_format: str = "json",
    fix: bool = False,
) -> list[str]:
    """Build the ruff CLI command list."""
    cmd = [ruff_binary, "check"]
    if fix:
        cmd.append("--fix")
    cmd.extend(["--output-format", output_format])
    if select:
        cmd.extend(["--select", ",".join(select)])
    if extra_args:
        cmd.extend(extra_args)
    cmd.extend(target_directories)
    return cmd


@log_function_call
def run_ruff_check_impl(
    ruff_binary: str,
    project_dir: str,
    target_directories: list[str],
    select: list[str] | None = None,
    extra_args: list[str] | None = None,
    max_issues: int = 1,
) -> str:
    """Run ruff check (read-only) and return formatted report.

    Returns:
        LLM-formatted report string, or "No issues found" message.
    """
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    cmd = _build_ruff_command(
        ruff_binary,
        target_directories,
        select,
        extra_args,
    )
    result = execute_command(cmd, cwd=project_dir)

    if result.execution_error:
        return f"Ruff execution error: {result.execution_error}"

    if result.timed_out:
        return "Ruff timed out."

    if result.return_code == 2:
        return f"Ruff error: {result.stderr}"

    messages, parse_error = parse_ruff_json_output(result.stdout, project_dir)
    if parse_error:
        return parse_error

    report = format_ruff_check_report(messages, max_issues)
    return report or "No ruff issues found."


@log_function_call
def run_ruff_fix_impl(
    ruff_binary: str,
    project_dir: str,
    target_directories: list[str],
    select: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> str:
    """Run ruff check --fix (modifies files) and return fix report.

    Warning:
        This modifies files in-place.

    Returns:
        Report with changed file list + remaining unfixed errors.
    """
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    # Pre-check to identify fixable files
    check_cmd = _build_ruff_command(
        ruff_binary,
        target_directories,
        select,
        extra_args,
    )
    check_result = execute_command(check_cmd, cwd=project_dir)

    if check_result.execution_error:
        return f"Ruff execution error: {check_result.execution_error}"

    if check_result.timed_out:
        return "Ruff timed out."

    if check_result.return_code == 2:
        return f"Ruff error: {check_result.stderr}"

    pre_messages, parse_error = parse_ruff_json_output(check_result.stdout, project_dir)
    if parse_error:
        return parse_error

    changed_files = sorted({m.filename for m in pre_messages if m.fixable})

    if not changed_files:
        return "No fixable violations found — no files modified."

    # Apply fixes
    fix_cmd = _build_ruff_command(
        ruff_binary,
        target_directories,
        select,
        extra_args,
        fix=True,
    )
    fix_result = execute_command(fix_cmd, cwd=project_dir)

    if fix_result.execution_error:
        return f"Ruff fix execution error: {fix_result.execution_error}"

    if fix_result.timed_out:
        return "Ruff fix timed out."

    if fix_result.return_code == 2:
        return f"Ruff fix error: {fix_result.stderr}"

    remaining, parse_error = parse_ruff_json_output(fix_result.stdout, project_dir)
    if parse_error:
        return f"Ruff applied fixes but could not parse remaining issues: {parse_error}"

    return format_ruff_fix_report(changed_files, remaining)
