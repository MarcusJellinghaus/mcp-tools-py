"""
Subprocess execution utilities with MCP STDIO isolation support.

This module provides functions for executing command-line tools with proper
timeout handling and STDIO isolation for Python commands in MCP server contexts.
"""

import logging
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

# Re-export subprocess exceptions for callers
from subprocess import CalledProcessError, SubprocessError, TimeoutExpired
from typing import Any, Callable

import structlog

from mcp_tools_py.log_utils import log_function_call

logger = logging.getLogger(__name__)
structured_logger = structlog.get_logger(__name__)

__all__ = [
    "CommandResult",
    "CommandOptions",
    "MAX_STDERR_IN_ERROR",
    "check_tool_missing_error",
    "execute_command",
    "execute_subprocess",
    "launch_process",
    "truncate_stderr",
    "CalledProcessError",
    "SubprocessError",
    "TimeoutExpired",
]


MAX_STDERR_IN_ERROR: int = 500


def check_tool_missing_error(
    stderr: str, tool_name: str, python_path: str
) -> str | None:
    """Check if stderr indicates the tool is not installed.

    Args:
        stderr: The stderr output from the subprocess.
        tool_name: The name of the tool (e.g., 'pytest', 'pylint', 'mypy').
        python_path: The path to the Python executable used.

    Returns:
        An actionable error message if the tool is missing, or None.
    """
    if f"No module named {tool_name}" in stderr:
        return (
            f"{tool_name} is not installed in the configured Python environment "
            f"({python_path}). Ensure --python-executable and --venv-path point "
            f"to the environment where {tool_name} is installed."
        )
    return None


def truncate_stderr(stderr: str, max_len: int = MAX_STDERR_IN_ERROR) -> str:
    """Truncate stderr to a maximum length.

    Args:
        stderr: The stderr string to truncate.
        max_len: Maximum length before truncation.

    Returns:
        The stderr string, truncated with '...' if it exceeds max_len.
    """
    if len(stderr) > max_len:
        return stderr[:max_len] + "..."
    return stderr


@dataclass
class CommandResult:
    """Represents the result of a command execution."""

    return_code: int
    stdout: str
    stderr: str
    timed_out: bool
    execution_error: str | None = None
    command: list[str] | None = field(default=None)
    runner_type: str | None = field(default=None)
    execution_time_ms: int | None = field(default=None)


@dataclass
class CommandOptions:
    """Configuration options for command execution.

    Attributes:
        cwd: Working directory for the subprocess
        timeout_seconds: Maximum time to wait for process completion
        env: Environment variables for the subprocess. May contain internal
             testing flags prefixed with underscore (e.g., _DISABLE_STDIO_ISOLATION)
             that should NEVER be used in production code.
        env_remove: List of environment variable names to remove
        capture_output: Whether to capture stdout and stderr
        text: Whether to decode output as text
        check: Whether to raise exception on non-zero exit code
        shell: Whether to execute through shell
        input_data: Data to send to subprocess stdin

    Warning:
        Environment variables starting with underscore (_) are internal testing
        flags that bypass safety mechanisms. They must not be used in production.
    """

    cwd: str | None = None
    timeout_seconds: int = 120
    env: dict[str, str] | None = None
    capture_output: bool = True
    text: bool = True
    check: bool = False
    shell: bool = False
    input_data: str | None = None
    env_remove: list[str] | None = None


def is_python_command(command: list[str]) -> bool:
    """Check if a command is a Python execution command."""
    if not command:
        return False

    executable = Path(command[0]).name.lower()
    return (
        executable in ["python", "python3", "python.exe", "python3.exe"]
        or command[0] == sys.executable
    )


def get_python_isolation_env() -> dict[str, str]:
    """Get environment variables for Python subprocess isolation."""
    env = os.environ.copy()

    # Python-specific settings to prevent MCP STDIO conflicts
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONNOUSERSITE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONSTARTUP": "",
        }
    )

    # Remove MCP-specific variables
    for var in ["MCP_STDIO_TRANSPORT", "MCP_SERVER_NAME", "MCP_CLIENT_PARAMS"]:
        env.pop(var, None)

    return env


def get_utf8_env() -> dict[str, str]:
    """Get base environment with UTF-8 encoding for non-Python commands.

    Returns:
        A copy of the current environment with UTF-8 encoding variables set.
    """
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if sys.platform == "win32":
        env["PYTHONLEGACYWINDOWSFSENCODING"] = "utf-8"
    else:
        env["LC_ALL"] = "C.UTF-8"
    return env


def prepare_env(
    command: list[str] | str,
    env: dict[str, str] | None = None,
    env_remove: list[str] | None = None,
) -> dict[str, str]:
    """Prepare consolidated environment for subprocess execution.

    Always starts from os.environ.copy() (via helper), then merges caller env
    on top. This fixes the bug where caller env would replace the entire
    parent environment.

    Args:
        command: The command to execute (used to detect Python commands).
        env: Optional caller-provided environment variables to merge.
        env_remove: Optional list of environment variable names to remove.

    Returns:
        A dict with the full inherited environment plus caller overrides.
    """
    if isinstance(command, list) and is_python_command(command):
        base = get_python_isolation_env()
    else:
        base = get_utf8_env()
    if env:
        base.update(env)
    if env_remove:
        for key in env_remove:
            base.pop(key, None)
    # Unconditionally remove CLAUDECODE recursion guard
    base.pop("CLAUDECODE", None)
    return base


def _safe_preexec_fn() -> None:
    """
    Safely attempt to create a new session.

    This is used on Unix-like systems to isolate the subprocess.
    Errors are silently ignored as they may occur in restricted environments.
    """
    try:
        if hasattr(os, "setsid"):
            os.setsid()
    except (OSError, PermissionError, AttributeError):
        # Ignore errors - may already be session leader or restricted env
        pass


def _run_subprocess(
    command: list[str], options: CommandOptions, use_stdio_isolation: bool = False
) -> subprocess.CompletedProcess[str]:
    """
    Internal function to run subprocess with or without STDIO isolation.

    Args:
        command: Command to execute
        options: Execution options
        use_stdio_isolation: Whether to use file-based STDIO isolation

    Returns:
        CompletedProcess with execution results
    """
    # Prepare environment
    env = options.env or os.environ.copy()
    if is_python_command(command):
        env = get_python_isolation_env()
        if options.env:
            env.update(options.env)

    # Handle input data and stdin
    stdin_value = subprocess.DEVNULL if options.input_data is None else None

    # Prepare preexec_fn for Unix-like systems
    preexec_fn: Callable[[], Any] | None = None
    start_new_session = False
    if os.name != "nt":
        preexec_fn = _safe_preexec_fn
        start_new_session = True

    # Use file-based STDIO for Python commands if needed
    if use_stdio_isolation and options.capture_output:
        with tempfile.TemporaryDirectory() as temp_dir:
            stdout_file = Path(temp_dir) / "stdout.txt"
            stderr_file = Path(temp_dir) / "stderr.txt"

            process = None
            stdout_f = None
            stderr_f = None

            try:
                # Open files
                stdout_f = open(stdout_file, "w", encoding="utf-8")
                stderr_f = open(stderr_file, "w", encoding="utf-8")

                # Use Popen for better process control
                popen_proc = None
                try:
                    popen_proc = subprocess.Popen(
                        command,
                        stdout=stdout_f,
                        stderr=stderr_f,
                        stdin=(
                            stdin_value
                            if options.input_data is None
                            else subprocess.PIPE
                        ),
                        cwd=options.cwd,
                        text=options.text,
                        env=env,
                        shell=options.shell,
                        start_new_session=start_new_session,
                        preexec_fn=preexec_fn,
                    )

                    # Communicate with timeout
                    try:
                        _, _ = popen_proc.communicate(
                            input=options.input_data, timeout=options.timeout_seconds
                        )
                        process = subprocess.CompletedProcess(
                            args=command,
                            returncode=popen_proc.returncode,
                            stdout="",  # Will be read from file
                            stderr="",  # Will be read from file
                        )
                    except subprocess.TimeoutExpired:
                        # Kill the process and all children
                        if popen_proc:
                            structured_logger.warning(
                                "Killing timed out process",
                                pid=popen_proc.pid,
                                command=command[:3] if command else None,
                            )

                            # On Windows, use taskkill to kill process tree
                            if os.name == "nt":
                                try:
                                    # Kill process tree on Windows
                                    subprocess.run(
                                        [
                                            "taskkill",
                                            "/F",
                                            "/T",
                                            "/PID",
                                            str(popen_proc.pid),
                                        ],
                                        capture_output=True,
                                        timeout=5,
                                    )
                                except (
                                    subprocess.SubprocessError,
                                    subprocess.TimeoutExpired,
                                    Exception,
                                ) as e:
                                    # Fallback to terminate/kill
                                    structured_logger.debug(
                                        "Taskkill failed, using fallback",
                                        error=str(e),
                                        pid=popen_proc.pid,
                                    )
                                    popen_proc.terminate()
                                    time.sleep(0.5)
                                    if popen_proc.poll() is None:
                                        popen_proc.kill()
                            else:
                                # On Unix, kill the process group
                                try:
                                    # Check if killpg and getpgid are available (Unix-only)
                                    if (
                                        hasattr(os, "killpg")
                                        and hasattr(os, "getpgid")
                                        and hasattr(signal, "SIGTERM")
                                        and hasattr(signal, "SIGKILL")
                                    ):
                                        os.killpg(os.getpgid(popen_proc.pid), signal.SIGTERM)  # type: ignore[attr-defined]  # needed for Windows
                                        time.sleep(0.5)
                                        if popen_proc.poll() is None:
                                            os.killpg(os.getpgid(popen_proc.pid), signal.SIGKILL)  # type: ignore[attr-defined]  # needed for Windows
                                    else:
                                        # Fallback for systems without killpg/getpgid
                                        popen_proc.terminate()
                                        time.sleep(0.5)
                                        if popen_proc.poll() is None:
                                            popen_proc.kill()
                                except (
                                    OSError,
                                    ProcessLookupError,
                                    AttributeError,
                                ) as e:
                                    # Fallback to terminate/kill
                                    structured_logger.debug(
                                        "Process group kill failed, using fallback",
                                        error=str(e),
                                        pid=popen_proc.pid,
                                    )
                                    popen_proc.terminate()
                                    time.sleep(0.5)
                                    if popen_proc.poll() is None:
                                        popen_proc.kill()

                            # Wait a bit for cleanup
                            try:
                                popen_proc.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                pass

                        # Re-raise the timeout exception
                        raise

                except subprocess.TimeoutExpired:
                    # Close files before re-raising to prevent Windows file locking
                    if stdout_f:
                        stdout_f.flush()
                        stdout_f.close()
                    if stderr_f:
                        stderr_f.flush()
                        stderr_f.close()

                    # On Windows, add a small delay to help with file handle cleanup
                    if os.name == "nt":
                        time.sleep(0.1)  # Give Windows time to release handles

                    # Re-raise to be handled by the caller
                    raise
                finally:
                    # Ensure files are closed
                    if stdout_f and not stdout_f.closed:
                        stdout_f.close()
                    if stderr_f and not stderr_f.closed:
                        stderr_f.close()
            except subprocess.TimeoutExpired:
                # This will be caught by the outer execute_subprocess
                raise
            except Exception:
                # For any other exception, ensure files are closed
                if stdout_f and not stdout_f.closed:
                    stdout_f.close()
                if stderr_f and not stderr_f.closed:
                    stderr_f.close()
                raise

            # Read output files after process completes
            # Use a small delay on Windows to avoid file locking issues
            if os.name == "nt":
                time.sleep(0.2)  # Increased delay for Windows

            # Read output files, handling potential errors
            stdout = ""
            stderr = ""

            try:
                if stdout_file.exists():
                    stdout = stdout_file.read_text(encoding="utf-8")
            except (OSError, PermissionError) as exc:
                # If we can't read the file, leave stdout empty
                logger.debug("Could not read stdout file: %s", exc)

            try:
                if stderr_file.exists():
                    stderr = stderr_file.read_text(encoding="utf-8")
            except (OSError, PermissionError) as exc:
                # If we can't read the file, leave stderr empty
                logger.debug("Could not read stderr file: %s", exc)

            # Update the process with the actual output read from files
            # If process is None (shouldn't happen), use default returncode of 1
            return subprocess.CompletedProcess(
                args=command,
                returncode=process.returncode if process else 1,
                stdout=stdout,
                stderr=stderr,
            )
    else:
        # Regular execution with better process cleanup
        popen_proc = None
        try:
            if options.capture_output:
                popen_proc = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=(
                        stdin_value if options.input_data is None else subprocess.PIPE
                    ),
                    cwd=options.cwd,
                    text=options.text,
                    env=env,
                    shell=options.shell,
                    start_new_session=start_new_session,
                    preexec_fn=preexec_fn,
                )

                try:
                    stdout, stderr = popen_proc.communicate(
                        input=options.input_data, timeout=options.timeout_seconds
                    )
                    return subprocess.CompletedProcess(
                        args=command,
                        returncode=popen_proc.returncode,
                        stdout=stdout or "",
                        stderr=stderr or "",
                    )
                except subprocess.TimeoutExpired:
                    # Kill the process tree on timeout
                    if popen_proc:
                        structured_logger.warning(
                            "Killing timed out process (regular execution)",
                            pid=popen_proc.pid,
                            command=command[:3] if command else None,
                        )

                        if os.name == "nt":
                            # Windows: Kill process tree
                            try:
                                subprocess.run(
                                    [
                                        "taskkill",
                                        "/F",
                                        "/T",
                                        "/PID",
                                        str(popen_proc.pid),
                                    ],
                                    capture_output=True,
                                    timeout=5,
                                )
                            except (
                                subprocess.SubprocessError,
                                subprocess.TimeoutExpired,
                                Exception,
                            ) as e:
                                structured_logger.debug(
                                    "Taskkill failed in regular execution, using kill",
                                    error=str(e),
                                    pid=popen_proc.pid,
                                )
                                popen_proc.kill()
                        else:
                            # Unix: Kill process group
                            try:
                                # Check if killpg and getpgid are available (Unix-only)
                                if (
                                    hasattr(os, "killpg")
                                    and hasattr(os, "getpgid")
                                    and hasattr(signal, "SIGTERM")
                                    and hasattr(signal, "SIGKILL")
                                ):
                                    # Try graceful termination first (consistent with first timeout block)
                                    os.killpg(os.getpgid(popen_proc.pid), signal.SIGTERM)  # type: ignore[attr-defined]  # needed for Windows
                                    time.sleep(0.5)
                                    if popen_proc.poll() is None:
                                        # Force kill if still running
                                        os.killpg(os.getpgid(popen_proc.pid), signal.SIGKILL)  # type: ignore[attr-defined]  # needed for Windows
                                else:
                                    popen_proc.kill()
                            except (OSError, ProcessLookupError, AttributeError) as e:
                                structured_logger.debug(
                                    "Process group kill failed in regular execution, using kill",
                                    error=str(e),
                                    pid=popen_proc.pid,
                                )
                                popen_proc.kill()

                        # Wait for cleanup
                        try:
                            popen_proc.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            pass
                    raise
            else:
                # No output capture needed
                return subprocess.run(
                    command,
                    capture_output=False,
                    cwd=options.cwd,
                    text=options.text,
                    timeout=options.timeout_seconds,
                    env=env,
                    shell=options.shell,
                    stdin=stdin_value,
                    input=options.input_data,
                    start_new_session=start_new_session,
                    preexec_fn=preexec_fn,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            raise  # Re-raise for handling in execute_subprocess
        except Exception:
            raise


def execute_subprocess(
    command: list[str], options: CommandOptions | None = None
) -> CommandResult:
    """
    Execute a command with automatic STDIO isolation for Python commands.

    Args:
        command: Command and arguments as a list
        options: Execution options

    Returns:
        CommandResult with execution details
    """
    if command is None:
        raise TypeError("Command cannot be None")

    if options is None:
        options = CommandOptions()

    start_time = time.time()

    # Determine if we need STDIO isolation
    # INTERNAL TESTING FLAG: _DISABLE_STDIO_ISOLATION
    # ================================================
    # This flag is ONLY for internal testing purposes to disable STDIO isolation
    # for Python commands. It allows tests to verify subprocess behavior without
    # the file-based STDIO redirection that's normally applied to Python commands.
    #
    # WHEN TO USE:
    # - Only in unit tests that need to test raw subprocess behavior
    # - When testing concurrent subprocess execution where file locking might interfere
    # - For performance testing where STDIO isolation overhead needs to be excluded
    #
    # HOW IT WORKS:
    # - Set environment variable _DISABLE_STDIO_ISOLATION=1 to disable isolation
    # - Python commands will then use direct subprocess pipes instead of temp files
    # - This bypasses the MCP STDIO conflict prevention mechanism
    #
    # WARNING: DO NOT USE IN PRODUCTION!
    # - This flag bypasses important isolation mechanisms
    # - Using it in production may cause STDIO conflicts with MCP servers
    # - It can lead to output corruption when Python subprocesses are involved
    # - This is an internal implementation detail that may change without notice
    #
    # Example (TEST ONLY):
    #   options = CommandOptions(env={"_DISABLE_STDIO_ISOLATION": "1"})
    #   result = execute_subprocess([sys.executable, "script.py"], options)
    disable_isolation = (
        options.env and options.env.get("_DISABLE_STDIO_ISOLATION") == "1"
    )
    use_isolation = is_python_command(command) and not disable_isolation

    structured_logger.debug(
        "Starting subprocess execution",
        command=command[:3] if command else None,
        cwd=options.cwd,
        timeout_seconds=options.timeout_seconds,
        use_isolation=use_isolation,
    )

    try:
        process = _run_subprocess(command, options, use_isolation)

        # Handle check parameter
        if options.check and process.returncode != 0:
            raise subprocess.CalledProcessError(
                process.returncode, command, process.stdout, process.stderr
            )

        execution_time_ms = int((time.time() - start_time) * 1000)

        return CommandResult(
            return_code=process.returncode,
            stdout=process.stdout or "",
            stderr=process.stderr or "",
            timed_out=False,
            command=command,
            runner_type="subprocess",
            execution_time_ms=execution_time_ms,
        )

    except subprocess.TimeoutExpired:
        execution_time_ms = int((time.time() - start_time) * 1000)
        return CommandResult(
            return_code=1,
            stdout="",
            stderr="",
            timed_out=True,
            execution_error=f"Process timed out after {options.timeout_seconds} seconds",
            command=command,
            runner_type="subprocess",
            execution_time_ms=execution_time_ms,
        )

    except subprocess.CalledProcessError as e:
        if options.check:
            raise
        execution_time_ms = int((time.time() - start_time) * 1000)
        return CommandResult(
            return_code=e.returncode,
            stdout=getattr(e, "stdout", "") or "",
            stderr=getattr(e, "stderr", "") or "",
            timed_out=False,
            command=command,
            runner_type="subprocess",
            execution_time_ms=execution_time_ms,
        )

    except Exception as e:
        # Handle all other exceptions (FileNotFoundError, PermissionError, etc.)
        execution_time_ms = int((time.time() - start_time) * 1000)
        structured_logger.error(
            "Subprocess execution failed",
            error=str(e),
            error_type=type(e).__name__,
            command_preview=command[:3] if command else None,
        )
        return CommandResult(
            return_code=1,
            stdout="",
            stderr="",
            timed_out=False,
            execution_error=f"{type(e).__name__}: {e}",
            command=command,
            runner_type="subprocess",
            execution_time_ms=execution_time_ms,
        )


def _run_heartbeat(
    stop_event: threading.Event,
    interval: int,
    message: str,
    start_time: float,
) -> None:
    """Daemon thread target for periodic logging during long-running subprocesses.

    Args:
        stop_event: Event to signal the heartbeat to stop.
        interval: Seconds between heartbeat log messages.
        message: Message to include in each heartbeat log.
        start_time: The time.time() when the subprocess started.
    """
    while not stop_event.wait(interval):
        elapsed = time.time() - start_time
        minutes, seconds = divmod(int(elapsed), 60)
        logger.info("%s (elapsed: %dm %ds)", message, minutes, seconds)


def launch_process(
    command: list[str] | str,
    cwd: str | Path | None = None,
    shell: bool = False,
    env: dict[str, str] | None = None,
    env_remove: list[str] | None = None,
) -> int:
    """Fire-and-forget process launcher using prepare_env().

    Args:
        command: The command to execute.
        cwd: Working directory for the subprocess.
        shell: Whether to execute through shell.
        env: Optional caller-provided environment variables to merge.
        env_remove: Optional list of environment variable names to remove.

    Returns:
        The PID of the launched process.
    """
    merged_env = prepare_env(command, env, env_remove)
    process = subprocess.Popen(
        command,
        cwd=cwd,
        shell=shell,
        env=merged_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process.pid


def execute_command(
    command: list[str],
    cwd: str | None = None,
    timeout_seconds: int = 120,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """
    Execute a command with automatic STDIO isolation for Python commands.

    Args:
        command: Complete command as list (e.g., ["python", "-m", "pylint", "src"])
        cwd: Working directory for subprocess
        timeout_seconds: Timeout in seconds
        env: Optional environment variables

    Returns:
        CommandResult with execution details and output
    """
    options = CommandOptions(
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        env=env,
    )
    return execute_subprocess(command, options)
