"""Main entry point for the Code Checker MCP server."""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from mcp_tools_py import __version__  # pylint: disable=no-name-in-module
from mcp_tools_py.log_utils import setup_logging
from mcp_tools_py.server import create_server

# Create logger
logger = logging.getLogger(__name__)


def _positive_timeout(value: str) -> int:
    """Parse --check-timeout as a positive integer.

    Args:
        value: Raw command line value.

    Returns:
        The parsed timeout in seconds.

    Raises:
        argparse.ArgumentTypeError: If the value is not a positive integer.
    """
    message = f"--check-timeout must be a positive integer, got {value!r}"
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(message) from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError(message)
    return parsed


def _build_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser.

    Returns:
        The configured parser
    """
    parser = argparse.ArgumentParser(
        description="MCP Tools Py Server - Run pylint, pytest, and mypy checks on Python code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcp-tools-py --project-dir /path/to/project
  mcp-tools-py --project-dir . --log-level DEBUG --keep-temp-files
  mcp-tools-py --project-dir /path/to/project --python-executable .venv/Scripts/python.exe --test-folder tests
        """,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--project-dir",
        type=str,
        required=True,
        help="Base directory for code checking operations (required)",
    )
    parser.add_argument(
        "--python-executable",
        type=str,
        help=(
            "Path to the Python interpreter that runs the checker tools. "
            "pytest, pylint, mypy, black and isort run through it, while ruff, "
            "bandit, vulture, tach and lint-imports are located next to it, so "
            "it should point to the environment where they are installed (the "
            "tool's own venv), not the project's runtime venv. A path that "
            "neither exists nor resolves on PATH fails at startup. "
            "Defaults to the current Python interpreter (sys.executable)"
        ),
    )
    parser.add_argument(
        "--venv-path",
        type=str,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--test-folder",
        type=str,
        default="tests",
        help="Path to the test folder (relative to project_dir). Defaults to 'tests'",
    )
    parser.add_argument(
        "--keep-temp-files",
        action="store_true",
        help="Keep temporary files after test execution. Useful for debugging when tests fail",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help=(
            "Path for structured JSON logs "
            "(default: mcp_tools_py_{timestamp}.log in project_dir/logs/)."
        ),
    )
    parser.add_argument(
        "--console-only",
        action="store_true",
        help="Log only to console, ignore --log-file parameter.",
    )
    parser.add_argument(
        "--refactoring-timeout",
        type=int,
        default=120,
        help="Timeout in seconds for rope refactoring operations (default: 120)",
    )
    parser.add_argument(
        "--check-timeout",
        type=_positive_timeout,
        default=None,
        help=(
            "Timeout in seconds for every checker and formatter subprocess "
            "(default: 120, pytest 300). A per-tool value in [tool.mcp-tools-py] "
            "in the project's pyproject.toml overrides it"
        ),
    )
    parser.add_argument(
        "--vulture-whitelist",
        type=str,
        default="vulture_whitelist.py",
        help=(
            "Path to vulture whitelist file relative to project_dir. "
            "Auto-included when the file exists. Default: vulture_whitelist.py"
        ),
    )
    return parser


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed arguments
    """
    return _build_parser().parse_args()


def main() -> None:
    """Main entry point for the MCP server."""
    # Parse command line arguments
    args = parse_args()

    # Validate project directory first
    project_dir = Path(args.project_dir)
    if not project_dir.exists() or not project_dir.is_dir():
        print(
            f"Error: Project directory does not exist or is not a directory: {project_dir}"
        )
        sys.exit(1)

    # Convert to absolute path
    project_dir = project_dir.absolute()

    # Generate default log file path if not specified
    if args.console_only:
        log_file = None
    elif args.log_file:
        log_file = args.log_file
    else:
        # Create default log file in project_dir/logs/ with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        logs_dir = project_dir / "logs"
        log_file = str(logs_dir / f"mcp_tools_py_{timestamp}.log")

    # Configure logging now that we have the project directory
    setup_logging(args.log_level, log_file)

    # Add debug logging after logger is initialized
    logger.debug("Logger initialized", extra={"log_level": args.log_level})

    logger.info(
        "Starting MCP Tools Py server",
        extra={
            "project_dir": str(project_dir),
            "log_level": args.log_level,
            "log_file": log_file,
        },
    )

    if args.venv_path:
        logger.warning(
            "--venv-path is deprecated and will be removed; use --python-executable. "
            "It still resolves the interpreter but no longer affects tool detection.",
            extra={"venv_path": args.venv_path},
        )

    # Create and run the server
    server = create_server(
        project_dir,
        python_executable=args.python_executable,
        venv_path=args.venv_path,
        test_folder=args.test_folder,
        keep_temp_files=args.keep_temp_files,
        refactoring_timeout=args.refactoring_timeout,
        vulture_whitelist=args.vulture_whitelist,
        check_timeout=args.check_timeout,
    )

    logger.info("Starting MCP server")
    logger.debug("About to call server.run()", extra={"project_dir": str(project_dir)})
    server.run()
    logger.debug(
        "After server.run() call - this line will only execute if server.run() returns"
    )


if __name__ == "__main__":
    main()
