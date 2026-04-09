"""Functions for running ruff check and ruff fix."""

import logging

from mcp_tools_py.code_checker_ruff.parsers import parse_ruff_json_output
from mcp_tools_py.code_checker_ruff.reporting import (
    format_ruff_check_report,
    format_ruff_fix_report,
)
from mcp_tools_py.utils.subprocess_runner import execute_command

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

    pre_messages, _ = parse_ruff_json_output(check_result.stdout, project_dir)
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

    remaining, _ = parse_ruff_json_output(fix_result.stdout, project_dir)
    return format_ruff_fix_report(changed_files, remaining)
