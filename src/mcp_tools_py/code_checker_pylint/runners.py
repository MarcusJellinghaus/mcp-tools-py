"""
Functions for running pylint analysis and processing results.
"""

import logging
import os
from typing import List, Optional

import structlog

from mcp_tools_py.code_checker_pylint.models import PylintResult
from mcp_tools_py.code_checker_pylint.parsers import parse_pylint_json_output
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.subprocess_runner import (
    check_tool_missing_error,
    execute_command,
    truncate_stderr,
)

logger = logging.getLogger(__name__)
structured_logger = structlog.get_logger(__name__)


@log_function_call
def get_pylint_results(
    project_dir: str,
    python_executable: str,
    extra_args: Optional[List[str]] = None,
    target_directories: Optional[List[str]] = None,
) -> PylintResult:
    """
    Runs pylint on the specified project directory and returns the results.

    Args:
        project_dir: The path to the project directory.
        extra_args: Optional list of extra pylint arguments to pass directly.
            Examples: ["--disable=C0114,C0116"], ["--enable=W0613", "--disable=C"]
        python_executable: Path to Python executable to use for running pylint. Already resolved by server.
        target_directories: List of directories to analyze relative to project_dir.
            Defaults to ["src"] and conditionally "tests" if it exists.
            Examples: ["src"], ["src", "tests"], ["mypackage", "tests"], ["."]

    Returns:
        A PylintResult object containing the results of the pylint run.

    Raises:
        FileNotFoundError: If the project directory does not exist.
    """
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    # Set default target directories if none provided
    if target_directories is None:
        target_directories = ["src"]
        if os.path.exists(os.path.join(project_dir, "tests")):
            target_directories.append("tests")

    # Validate that target directories exist
    valid_directories = []
    for directory in target_directories:
        full_path = os.path.join(project_dir, directory)
        if os.path.exists(full_path):
            valid_directories.append(directory)
        else:
            structured_logger.warning(
                "Target directory does not exist, skipping",
                directory=directory,
                full_path=full_path,
            )

    if not valid_directories:
        error_message = (
            f"No valid target directories found. Checked: {target_directories}"
        )
        structured_logger.error(
            "No valid directories to analyze",
            target_directories=target_directories,
            project_dir=project_dir,
        )
        return PylintResult(
            return_code=1,
            messages=[],
            error=error_message,
            raw_output=None,
        )

    structured_logger.info(
        "Starting pylint analysis",
        project_dir=project_dir,
        extra_args=extra_args,
        target_directories=valid_directories,
    )

    # Construct the pylint command
    pylint_command = [
        python_executable,
        "-m",
        "pylint",
        "--output-format=json",
    ]

    if extra_args:
        pylint_command.extend(extra_args)

    # Add all valid target directories
    pylint_command.extend(valid_directories)

    # Execute the subprocess
    subprocess_result = execute_command(
        command=pylint_command, cwd=project_dir, timeout_seconds=120
    )

    # Handle subprocess execution errors
    if subprocess_result.execution_error:
        stderr = subprocess_result.stderr or ""
        tool_error = check_tool_missing_error(stderr, "pylint", python_executable)
        if tool_error:
            return PylintResult(
                return_code=subprocess_result.return_code,
                messages=[],
                error=tool_error,
                raw_output=None,
            )
        error_msg = subprocess_result.execution_error
        if stderr.strip():
            error_msg += f" stderr: {truncate_stderr(stderr.strip())}"
        return PylintResult(
            return_code=subprocess_result.return_code,
            messages=[],
            error=error_msg,
            raw_output=None,
        )

    if subprocess_result.timed_out:
        return PylintResult(
            return_code=1,
            messages=[],
            error="Pylint execution timed out after 120 seconds",
            raw_output=None,
        )

    # Log subprocess results
    structured_logger.info(
        "Pylint subprocess completed",
        return_code=subprocess_result.return_code,
        has_stdout=bool(subprocess_result.stdout),
        has_stderr=bool(subprocess_result.stderr),
        stdout_empty=not subprocess_result.stdout
        or subprocess_result.stdout.strip() == "",
        stderr_empty=not subprocess_result.stderr
        or subprocess_result.stderr.strip() == "",
        command_executed=" ".join(pylint_command),
    )

    raw_output = subprocess_result.stdout

    # Parse pylint output from JSON
    messages, parse_error = parse_pylint_json_output(raw_output)

    if parse_error:
        return PylintResult(
            return_code=subprocess_result.return_code,
            messages=[],
            error=parse_error,
            raw_output=raw_output,
        )

    result = PylintResult(
        return_code=subprocess_result.return_code,
        messages=messages,
        raw_output=raw_output,
    )

    structured_logger.info(
        "Pylint analysis completed",
        return_code=subprocess_result.return_code,
        messages_count=len(messages),
        unique_codes=len(result.get_message_ids()),
    )

    return result
