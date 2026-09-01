"""Functions for running bandit security analysis."""

import logging
import os
import shutil
import tempfile
from pathlib import Path

from mcp_tools_py.code_checker_bandit.models import BanditResult
from mcp_tools_py.code_checker_bandit.parsers import parse_bandit_json_output
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.subprocess_runner import execute_command

logger = logging.getLogger(__name__)


def _build_bandit_command(
    bandit_binary: str,
    target_directories: list[str],
    output_path: str,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build the bandit CLI command list.

    Returns:
        Command argv ready to pass to `execute_command`.
    """
    cmd = [bandit_binary, "-f", "json", "-o", output_path, "-r"]
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
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> BanditResult:
    """Run bandit and return structured result.

    Bandit writes its JSON report to a temp file via ``-o <file>``; the report
    is read back from that file rather than stdout, so a Rich progress bar on
    stdout cannot corrupt the parsed output.

    Args:
        bandit_binary: Path to the bandit executable.
        project_dir: Directory to run bandit in.
        target_directories: Directories to analyze.
        extra_args: Additional bandit CLI flags.
        timeout_seconds: Maximum seconds to wait for bandit.

    Returns:
        BanditResult with parsed messages, file errors, or execution error.

    Raises:
        FileNotFoundError: If the project directory does not exist.
    """
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    temp_dir = tempfile.mkdtemp(prefix="bandit_runner_")
    try:
        output_file = os.path.join(temp_dir, "bandit_result.json")
        cmd = _build_bandit_command(
            bandit_binary, target_directories, output_file, extra_args
        )
        result = execute_command(cmd, cwd=project_dir, timeout_seconds=timeout_seconds)

        if result.timed_out:
            return BanditResult(
                return_code=-1,
                messages=[],
                errors=[],
                error=f"timed out after {timeout_seconds} seconds",
            )

        if result.execution_error:
            return BanditResult(
                return_code=-1,
                messages=[],
                errors=[],
                error=str(result.execution_error),
            )

        if result.return_code > 1:
            return BanditResult(
                return_code=result.return_code,
                messages=[],
                errors=[],
                error=result.stderr,
            )

        if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
            return BanditResult(
                return_code=result.return_code,
                messages=[],
                errors=[],
                error=(
                    "bandit produced no JSON output file "
                    f"(exit code {result.return_code})"
                ),
            )

        content = Path(output_file).read_text(encoding="utf-8")
        messages, errors, parse_error = parse_bandit_json_output(content, project_dir)

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
            raw_output=content,
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
