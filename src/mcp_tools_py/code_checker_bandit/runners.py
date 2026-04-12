"""Functions for running bandit security analysis."""

import logging
import os

from mcp_coder_utils.subprocess_runner import execute_command

from mcp_tools_py.code_checker_bandit.models import BanditResult
from mcp_tools_py.code_checker_bandit.parsers import parse_bandit_json_output
from mcp_tools_py.log_utils import log_function_call

logger = logging.getLogger(__name__)


def _build_bandit_command(
    bandit_binary: str,
    target_directories: list[str],
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build the bandit CLI command list."""
    cmd = [bandit_binary, "-f", "json", "-r"]
    cmd.extend(target_directories)
    if extra_args:
        cmd.extend(extra_args)
    return cmd


@log_function_call
def run_bandit_check_impl(
    bandit_binary: str,
    project_dir: str,
    target_directories: list[str],
    extra_args: list[str] | None = None,
) -> BanditResult:
    """Run bandit and return structured result.

    Returns:
        BanditResult with parsed messages, file errors, or execution error.

    Raises:
        FileNotFoundError: If the project directory does not exist.
    """
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    cmd = _build_bandit_command(bandit_binary, target_directories, extra_args)
    result = execute_command(cmd, cwd=project_dir)

    if result.execution_error:
        return BanditResult(
            return_code=-1, messages=[], errors=[], error=str(result.execution_error)
        )

    if result.timed_out:
        return BanditResult(return_code=-1, messages=[], errors=[], error="timed out")

    if result.return_code > 1:
        return BanditResult(
            return_code=result.return_code,
            messages=[],
            errors=[],
            error=result.stderr,
        )

    messages, errors, parse_error = parse_bandit_json_output(result.stdout, project_dir)

    if parse_error:
        return BanditResult(
            return_code=result.return_code,
            messages=[],
            errors=[],
            error=parse_error,
        )

    return BanditResult(
        return_code=result.return_code,
        messages=messages,
        errors=errors,
        raw_output=result.stdout,
    )
