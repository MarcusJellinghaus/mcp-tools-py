"""Runner for mypy type checking."""

import logging
import os

from mcp_tools_py.log_utils import log_function_call
from mcp_coder_utils.subprocess_runner import (
    check_tool_missing_error,
    execute_command,
    truncate_stderr,
)

from mcp_tools_py.code_checker_mypy.models import MypyResult
from mcp_tools_py.code_checker_mypy.parsers import parse_mypy_json_output

logger = logging.getLogger(__name__)

# Default strict flags from tools/mypy.bat
STRICT_FLAGS = [
    "--strict",
    "--warn-redundant-casts",
    "--warn-unused-ignores",
    "--warn-unreachable",
    "--disallow-any-generics",
    "--disallow-untyped-defs",
    "--disallow-incomplete-defs",
    "--check-untyped-defs",
    "--disallow-untyped-decorators",
    "--no-implicit-optional",
    "--warn-return-any",
    "--no-implicit-reexport",
    "--strict-optional",
]


@log_function_call
def run_mypy_check(
    project_dir: str,
    python_executable: str,
    strict: bool = True,
    disable_error_codes: list[str] | None = None,
    target_directories: list[str] | None = None,
    follow_imports: str = "normal",
    cache_dir: str | None = None,
    config_file: str | None = None,
) -> MypyResult:
    """
    Run mypy type checking on project.

    Args:
        project_dir: Path to the project directory
        strict: Use strict mode settings (default: True)
        disable_error_codes: List of error codes to ignore (e.g., ['import', 'arg-type'])
        target_directories: Directories to check (auto-detected from pyproject.toml when None)
        follow_imports: How to handle imports ('normal', 'silent', 'skip', 'error')
        python_executable: Python interpreter to use (default: sys.executable)
        cache_dir: Custom cache directory for incremental checking
        config_file: Path to custom mypy config file

    Returns:
        MypyResult with execution results
    """
    if not os.path.isdir(project_dir):
        raise FileNotFoundError(f"Project directory not found: {project_dir}")

    # Convert to absolute path
    project_dir = os.path.abspath(project_dir)

    # Validate target directories exist
    valid_directories = []
    for directory in target_directories or []:
        full_path = os.path.join(project_dir, directory)
        if os.path.exists(full_path):
            valid_directories.append(directory)
        else:
            logger.warning("Target directory not found", extra={"directory": directory})

    # Set target directories
    mypy_targets = valid_directories

    if not mypy_targets:
        return MypyResult(
            return_code=1, messages=[], error="No valid target directories found"
        )

    # Build command
    command = [
        python_executable,
        "-m",
        "mypy",
        "--output",
        "json",
        "--no-color-output",
        "--show-column-numbers",
        "--show-error-codes",
        "--namespace-packages",  # Handle src layout properly
        "--explicit-package-bases",  # Fix duplicate module names issue
    ]

    # Add strict flags if requested
    if strict:
        command.extend(STRICT_FLAGS)

    # Add config file if specified
    if config_file and os.path.exists(os.path.join(project_dir, config_file)):
        command.extend(["--config-file", config_file])

    # Add cache directory
    if cache_dir:
        command.extend(["--cache-dir", cache_dir])

    # Add follow imports setting
    command.extend(["--follow-imports", follow_imports])

    # Disable specific error codes
    if disable_error_codes:
        for code in disable_error_codes:
            command.extend(["--disable-error-code", code])

    # Add target directories
    command.extend(mypy_targets)

    logger.info(
        "Starting mypy check",
        extra={
            "project_dir": project_dir,
            "strict": strict,
            "targets": mypy_targets,
            "command": " ".join(command),
        },
    )

    # Set MYPYPATH to src directory to handle module resolution correctly
    env = os.environ.copy()
    env["MYPYPATH"] = os.path.join(project_dir, "src")

    # Execute mypy
    result = execute_command(
        command=command, cwd=project_dir, timeout_seconds=120, env=env
    )

    # Check for missing mypy module early (before other error handling)
    stderr = result.stderr or ""
    tool_error = check_tool_missing_error(stderr, "mypy", python_executable)
    if tool_error:
        return MypyResult(return_code=result.return_code, messages=[], error=tool_error)

    # Handle execution errors
    if result.execution_error:
        error_msg = result.execution_error
        if stderr.strip():
            error_msg += f" stderr: {truncate_stderr(stderr.strip())}"
        return MypyResult(return_code=result.return_code, messages=[], error=error_msg)

    if result.timed_out:
        return MypyResult(
            return_code=1,
            messages=[],
            error="Mypy execution timed out after 120 seconds",
        )

    # Combine stdout and stderr for raw output when there are issues
    raw_output = result.stdout
    if result.stderr.strip():
        raw_output = (
            raw_output + "\n" + result.stderr if raw_output.strip() else result.stderr
        )

    # Parse output first to ensure messages variable is defined
    # For mypy config errors, check both stdout and stderr
    output_to_parse = result.stdout
    if result.return_code == 2 and not result.stdout.strip() and result.stderr.strip():
        # Mypy config errors often go to stderr
        output_to_parse = result.stderr

    messages, parse_error = parse_mypy_json_output(output_to_parse)

    # Log raw output for debugging when return code is 2
    if result.return_code == 2:
        logger.warning(
            "Mypy returned configuration error",
            extra={
                "return_code": result.return_code,
                "stdout_length": len(result.stdout),
                "stderr_length": len(result.stderr),
                "command": " ".join(command),
            },
        )
        # For configuration errors, include stderr in the error message
        if result.stderr.strip() and not messages:
            return MypyResult(
                return_code=result.return_code,
                messages=[],
                error=f"Mypy configuration error: {result.stderr.strip()}",
                raw_output=raw_output,
            )

    if parse_error:
        return MypyResult(
            return_code=result.return_code,
            messages=[],
            error=parse_error,
            raw_output=raw_output,
        )

    # Count statistics
    errors_found = len([m for m in messages if m.severity == "error"])

    mypy_result = MypyResult(
        return_code=result.return_code,
        messages=messages,
        raw_output=raw_output,
        errors_found=errors_found,
    )

    logger.info(
        "Mypy check completed",
        extra={
            "return_code": result.return_code,
            "total_messages": len(messages),
            "errors": errors_found,
        },
    )

    return mypy_result
