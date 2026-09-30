"""Functions for running ruff check and ruff fix."""

import logging
import os

from mcp_tools_py.code_checker_ruff.reporting import (
    format_ruff_check_report,
    format_ruff_fix_report,
)
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.ruff_parsing import parse_ruff_json_output
from mcp_tools_py.utils.subprocess_runner import execute_command

logger = logging.getLogger(__name__)

_STATISTICS_ERROR = (
    "--statistics changes ruff's output format and is not supported.\n"
    "Use the built-in rule counts in the summary instead."
)
_FIX_IN_CHECK_ERROR = (
    "{flag} modifies files and is not supported by run_ruff_check. "
    "Use run_ruff_fix instead."
)
_EXTRA_ARGS_HINT = " An argument in extra_args probably changed the output shape."


def _rejected_flag(extra_args: list[str] | None, flags: tuple[str, ...]) -> str | None:
    """First token in extra_args that exactly equals one of flags, else None."""
    return next((arg for arg in extra_args or [] if arg in flags), None)


def _rejection_message(flag: str) -> str:
    """Error returned instead of running ruff with a rejected flag."""
    if flag == "--statistics":
        return _STATISTICS_ERROR
    return _FIX_IN_CHECK_ERROR.format(flag=flag)


def _with_hint(parse_error: str, extra_args: list[str] | None) -> str:
    """Append the extra_args hint to a parse error when extra_args were passed."""
    return parse_error + _EXTRA_ARGS_HINT if extra_args else parse_error


def _build_ruff_command(
    ruff_binary: str,
    target_directories: list[str],
    select: list[str] | None = None,
    extra_args: list[str] | None = None,
    output_format: str = "json",
    fix: bool = False,
) -> list[str]:
    """Build the ruff CLI command list.

    Returns:
        Command argv ready to pass to `execute_command`.
    """
    cmd = [ruff_binary, "check"]
    if fix:
        cmd.append("--fix")
    cmd.extend(["--output-format", output_format])
    if select:
        cmd.extend(["--select", ",".join(select)])
    if extra_args:
        cmd.extend(extra_args)
    # Last flag wins in ruff: project config and extra_args cannot make a
    # non-fix command write files.
    cmd.extend(["--no-fix-only"] if fix else ["--no-fix", "--no-fix-only"])
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
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> str:
    """Run ruff check (read-only) and return formatted report.

    Returns:
        LLM-formatted report string, or "No issues found" message.

    Raises:
        FileNotFoundError: If `project_dir` does not exist.
    """
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    rejected = _rejected_flag(extra_args, ("--statistics", "--fix", "--fix-only"))
    if rejected:
        return _rejection_message(rejected)

    cmd = _build_ruff_command(
        ruff_binary,
        target_directories,
        select,
        extra_args,
    )
    result = execute_command(cmd, cwd=project_dir, timeout_seconds=timeout_seconds)

    if result.timed_out:
        return f"Ruff timed out after {timeout_seconds} seconds."

    if result.execution_error:
        return f"Ruff execution error: {result.execution_error}"

    if result.return_code == 2:
        return f"Ruff error: {result.stderr}"

    messages, parse_error = parse_ruff_json_output(result.stdout, project_dir)
    if parse_error:
        return _with_hint(parse_error, extra_args)

    report = format_ruff_check_report(messages, max_issues)
    return report or "No ruff issues found."


@log_function_call
def run_ruff_fix_impl(
    ruff_binary: str,
    project_dir: str,
    target_directories: list[str],
    select: list[str] | None = None,
    extra_args: list[str] | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> str:
    """Run ruff check --fix (modifies files) and return fix report.

    Warning:
        This modifies files in-place.

    Returns:
        Report with changed file list + remaining unfixed errors.

    Raises:
        FileNotFoundError: If `project_dir` does not exist.
    """
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    rejected = _rejected_flag(extra_args, ("--statistics",))
    if rejected:
        return _rejection_message(rejected)

    # Pre-check to identify fixable files
    check_cmd = _build_ruff_command(
        ruff_binary,
        target_directories,
        select,
        extra_args,
    )
    check_result = execute_command(
        check_cmd, cwd=project_dir, timeout_seconds=timeout_seconds
    )

    if check_result.timed_out:
        return f"Ruff timed out after {timeout_seconds} seconds."

    if check_result.execution_error:
        return f"Ruff execution error: {check_result.execution_error}"

    if check_result.return_code == 2:
        return f"Ruff error: {check_result.stderr}"

    pre_messages, parse_error = parse_ruff_json_output(check_result.stdout, project_dir)
    if parse_error:
        return _with_hint(parse_error, extra_args)

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
    fix_result = execute_command(
        fix_cmd, cwd=project_dir, timeout_seconds=timeout_seconds
    )

    if fix_result.timed_out:
        return f"Ruff fix timed out after {timeout_seconds} seconds."

    if fix_result.execution_error:
        return f"Ruff fix execution error: {fix_result.execution_error}"

    if fix_result.return_code == 2:
        return f"Ruff fix error: {fix_result.stderr}"

    remaining, parse_error = parse_ruff_json_output(fix_result.stdout, project_dir)
    if parse_error:
        return (
            "Ruff applied fixes but could not parse remaining issues: "
            f"{_with_hint(parse_error, extra_args)}"
        )

    return format_ruff_fix_report(changed_files, remaining)
