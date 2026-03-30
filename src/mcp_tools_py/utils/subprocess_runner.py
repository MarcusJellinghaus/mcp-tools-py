"""Subprocess execution utilities with MCP STDIO isolation support.

This module provides functions for executing command-line tools with proper
timeout handling and STDIO isolation for Python commands in MCP server contexts.
"""

import logging
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

# Re-export for external use (allows catching without direct subprocess import)
from subprocess import CalledProcessError, SubprocessError, TimeoutExpired

logger = logging.getLogger(__name__)

MAX_STDERR_IN_ERROR: int = 500

__all__ = [
    "CommandResult",
    "CommandOptions",
    "MAX_STDERR_IN_ERROR",
    "check_tool_missing_error",
    "execute_command",
    "execute_subprocess",
    "launch_process",
    "format_command",
    "truncate_stderr",
    # Re-exported exceptions
    "CalledProcessError",
    "SubprocessError",
    "TimeoutExpired",
]


def check_tool_missing_error(
    stderr: str, tool_name: str, python_path: str
) -> str | None:
    """Check if stderr indicates the tool is not installed.

    Returns:
        Error message string if the tool is missing, or None if no issue detected.
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

    Returns:
        The original stderr if within max_len, otherwise truncated with ellipsis.
    """
    if len(stderr) > max_len:
        return stderr[:max_len] + "..."
    return stderr


def format_command(command: list[str]) -> str:
    """Format a command list as a platform-aware shell string.

    Uses shlex.join() on Unix, subprocess.list2cmdline() on Windows.
    Truncates at 200 characters with '...' suffix.
    """
    if os.name == "nt":
        full = subprocess.list2cmdline(command)
    else:
        full = shlex.join(command)
    if len(full) > 200:
        return full[:200] + "..."
    return full


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
        env_remove: List of environment variable names to remove after merging
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
    """Check if a command is a Python execution command.

    Returns:
        True if the command runs a Python interpreter.
    """
    if not command:
        return False

    executable = Path(command[0]).name.lower()
    return (
        executable in ["python", "python3", "python.exe", "python3.exe"]
        or command[0] == sys.executable
    )


def get_python_isolation_env() -> dict[str, str]:
    """Get environment variables for Python subprocess isolation.

    Returns:
        Dict of environment variables with MCP isolation settings.
    """
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
    """Get environment variables for UTF-8 encoding support on all subprocess types.

    Returns:
        Dict of environment variables with UTF-8 encoding settings.
    """
    env = os.environ.copy()

    # Set UTF-8 encoding for all subprocess types
    env.update(
        {
            "PYTHONIOENCODING": "utf-8",
            "PYTHONUTF8": "1",
        }
    )

    # On Windows, also set legacy encoding variables
    if os.name == "nt":
        env.update(
            {
                "PYTHONLEGACYWINDOWSFSENCODING": "utf-8",
            }
        )
    else:
        # On Unix systems, set locale for UTF-8
        env.update(
            {
                "LC_ALL": "C.UTF-8",
            }
        )

    return env


def prepare_env(
    command: list[str] | str,
    env: dict[str, str] | None,
    env_remove: list[str] | None,
) -> dict[str, str]:
    """Build a complete environment dict for subprocess execution.

    Starts from os.environ, applies Python isolation or UTF-8 settings
    based on command type, merges caller-provided env on top, then
    removes any keys listed in env_remove.

    Args:
        command: Command as list or string. String commands are always
            treated as non-Python (shell=True implies unknown executable).
        env: Optional caller-provided environment variables to merge.
        env_remove: Optional list of environment variable names to remove.

    Returns:
        Complete environment dict ready for subprocess.Popen.
    """
    if isinstance(command, list) and is_python_command(command):
        result = get_python_isolation_env()
    else:
        result = get_utf8_env()

    if env:
        result.update(env)

    for key in env_remove or []:
        result.pop(key, None)

    return result


def _run_subprocess(  # pylint: disable=too-many-statements
    command: list[str], options: CommandOptions, use_stdio_isolation: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run subprocess with or without STDIO isolation.

    Args:
        command: Command to execute
        options: Execution options
        use_stdio_isolation: Whether to use file-based STDIO isolation

    Returns:
        CompletedProcess with execution results

    Raises:
        TimeoutExpired: If the subprocess exceeds the configured timeout.
    """
    # Track start time for timeout logging
    subprocess_start_time = time.time()
    env = prepare_env(command, options.env, options.env_remove)

    # Handle input data and stdin
    stdin_value = subprocess.DEVNULL if options.input_data is None else None

    # Use start_new_session for process isolation (thread-safe alternative to preexec_fn)
    start_new_session = os.name != "nt"  # True on Unix, False on Windows

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
                        encoding="utf-8" if options.text else None,
                        errors="replace",  # Replace invalid characters instead of crashing
                        env=env,
                        shell=options.shell,
                        start_new_session=start_new_session,
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
                            elapsed_time = time.time() - subprocess_start_time
                            cmd_display = " ".join(command[:3]) + (
                                "..." if len(command) > 3 else ""
                            )
                            logger.warning(
                                f"Killing timed out process (STDIO isolation, PID: {popen_proc.pid}): "
                                f"command='{cmd_display}', timeout={options.timeout_seconds}s, "
                                f"elapsed={elapsed_time:.1f}s, cwd='{options.cwd or 'current'}'"
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
                                        check=False,
                                    )
                                except (
                                    subprocess.SubprocessError,
                                    subprocess.TimeoutExpired,
                                    OSError,
                                ) as e:
                                    logger.debug(
                                        f"Taskkill failed, using fallback: {e}"
                                    )
                                    popen_proc.terminate()
                                    time.sleep(0.5)
                                    if popen_proc.poll() is None:
                                        popen_proc.kill()
                            else:
                                # On Unix, kill the process group
                                try:
                                    if (
                                        hasattr(os, "killpg")
                                        and hasattr(os, "getpgid")
                                        and hasattr(signal, "SIGTERM")
                                        and hasattr(signal, "SIGKILL")
                                    ):
                                        os.killpg(  # type: ignore[attr-defined,unused-ignore]
                                            os.getpgid(popen_proc.pid), signal.SIGTERM  # type: ignore[attr-defined,unused-ignore]
                                        )
                                        time.sleep(0.5)
                                        if popen_proc.poll() is None:
                                            os.killpg(  # type: ignore[attr-defined,unused-ignore]
                                                os.getpgid(popen_proc.pid),  # type: ignore[attr-defined,unused-ignore]
                                                signal.SIGKILL,  # type: ignore[attr-defined,unused-ignore]
                                            )
                                    else:
                                        popen_proc.terminate()
                                        time.sleep(0.5)
                                        if popen_proc.poll() is None:
                                            popen_proc.kill()
                                except (
                                    OSError,
                                    ProcessLookupError,
                                    AttributeError,
                                ) as e:
                                    logger.debug(
                                        f"Process group kill failed, using fallback: {e}"
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
                    # This cleanup is necessary before re-raising the timeout exception
                    if stdout_f:
                        stdout_f.flush()
                        stdout_f.close()
                    if stderr_f:
                        stderr_f.flush()
                        stderr_f.close()

                    # On Windows, add a small delay to help with file handle cleanup
                    if os.name == "nt":
                        time.sleep(0.1)

                    # Re-raise to be handled by the caller
                    raise  # pylint: disable=try-except-raise
                finally:
                    # Ensure files are closed
                    if stdout_f and not stdout_f.closed:
                        stdout_f.close()
                    if stderr_f and not stderr_f.closed:
                        stderr_f.close()
            except subprocess.TimeoutExpired:
                raise  # pylint: disable=try-except-raise
            except Exception:
                # Let any other exceptions propagate after cleanup in finally block
                raise  # pylint: disable=try-except-raise

            # Read output files after process completes
            # Use a small delay on Windows to avoid file locking issues
            if os.name == "nt":
                time.sleep(0.2)

            # Read output files, handling potential errors
            stdout = ""
            stderr = ""

            try:
                if stdout_file.exists():
                    stdout = stdout_file.read_text(encoding="utf-8")
            except (OSError, PermissionError) as exc:
                logger.debug(f"Could not read stdout file: {exc}")

            try:
                if stderr_file.exists():
                    stderr = stderr_file.read_text(encoding="utf-8")
            except (OSError, PermissionError) as exc:
                logger.debug(f"Could not read stderr file: {exc}")

            # Update the process with the actual output read from files
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
                    encoding="utf-8" if options.text else None,
                    errors="replace",  # Replace invalid characters instead of crashing
                    env=env,
                    shell=options.shell,
                    start_new_session=start_new_session,
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
                        elapsed_time = time.time() - subprocess_start_time
                        cmd_display = " ".join(command[:3]) + (
                            "..." if len(command) > 3 else ""
                        )
                        logger.warning(
                            f"Killing timed out process (regular execution, PID: {popen_proc.pid}): "
                            f"command='{cmd_display}', timeout={options.timeout_seconds}s, "
                            f"elapsed={elapsed_time:.1f}s, cwd='{options.cwd or 'current'}'"
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
                                    check=False,
                                )
                            except (
                                subprocess.SubprocessError,
                                subprocess.TimeoutExpired,
                                OSError,
                            ) as e:
                                logger.debug(
                                    f"Taskkill failed in regular execution: {e}"
                                )
                                popen_proc.kill()
                        else:
                            # Unix: Kill process group
                            try:
                                if (
                                    hasattr(os, "killpg")
                                    and hasattr(os, "getpgid")
                                    and hasattr(signal, "SIGTERM")
                                    and hasattr(signal, "SIGKILL")
                                ):
                                    os.killpg(  # type: ignore[attr-defined,unused-ignore]
                                        os.getpgid(popen_proc.pid), signal.SIGTERM  # type: ignore[attr-defined,unused-ignore]
                                    )
                                    time.sleep(0.5)
                                    if popen_proc.poll() is None:
                                        os.killpg(  # type: ignore[attr-defined,unused-ignore]
                                            os.getpgid(popen_proc.pid), signal.SIGKILL  # type: ignore[attr-defined,unused-ignore]
                                        )
                                else:
                                    popen_proc.kill()
                            except (OSError, ProcessLookupError, AttributeError) as e:
                                logger.debug(
                                    f"Process group kill failed in regular execution: {e}"
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
                    encoding="utf-8" if options.text else None,
                    errors="replace",  # Replace invalid characters instead of crashing
                    timeout=options.timeout_seconds,
                    env=env,
                    shell=options.shell,
                    stdin=stdin_value,
                    input=options.input_data,
                    start_new_session=start_new_session,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            raise  # pylint: disable=try-except-raise
        except Exception:
            # Re-raise any other exceptions (this catch-all is needed for cleanup)
            raise  # pylint: disable=try-except-raise


def _run_heartbeat(
    stop_event: threading.Event,
    interval: int,
    message: str,
    start_time: float,
) -> None:
    """Heartbeat loop — runs in a daemon thread, logs at regular intervals."""
    while not stop_event.wait(interval):
        elapsed = time.time() - start_time
        minutes, seconds = divmod(int(elapsed), 60)
        logger.info("%s (elapsed: %dm %ds)", message, minutes, seconds)


def execute_subprocess(
    command: list[str],
    options: CommandOptions | None = None,
    heartbeat_interval_seconds: int | None = None,
    heartbeat_message: str = "",
) -> CommandResult:
    """Execute a command with automatic STDIO isolation for Python commands.

    Args:
        command: Command and arguments as a list
        options: Execution options
        heartbeat_interval_seconds: If set and > 0, log a heartbeat message
            at this interval (in seconds) while the subprocess is running.
        heartbeat_message: Message to include in heartbeat log entries.

    Returns:
        CommandResult with execution details

    Raises:
        TypeError: If command is None.
        CalledProcessError: If check is True and the process returns non-zero exit code.
    """
    if command is None:
        raise TypeError("Command cannot be None")

    if not command:
        raise ValueError("Command cannot be empty")

    if options is None:
        options = CommandOptions()

    start_time = time.time()

    # Determine if we need STDIO isolation
    disable_isolation = (
        options.env and options.env.get("_DISABLE_STDIO_ISOLATION") == "1"
    )
    use_isolation = is_python_command(command) and not disable_isolation

    logger.debug(f"Starting subprocess execution: {command[:3] if command else None}")

    stop_event = None
    heartbeat_thread = None

    if heartbeat_interval_seconds and heartbeat_interval_seconds > 0:
        stop_event = threading.Event()
        heartbeat_thread = threading.Thread(
            target=_run_heartbeat,
            args=(
                stop_event,
                heartbeat_interval_seconds,
                heartbeat_message,
                start_time,
            ),
            daemon=True,
        )
        heartbeat_thread.start()

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

    except (FileNotFoundError, PermissionError, OSError) as e:
        # Handle file system and permission errors
        execution_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Subprocess execution failed: {type(e).__name__}: {e}")
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

    finally:
        if stop_event is not None:
            stop_event.set()
        if heartbeat_thread is not None:
            heartbeat_thread.join(timeout=2)


def execute_command(
    command: list[str],
    cwd: str | None = None,
    timeout_seconds: int = 120,
    env: dict[str, str] | None = None,
) -> CommandResult:
    """Execute a command with automatic STDIO isolation for Python commands.

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


def launch_process(
    command: list[str] | str,
    cwd: str | Path | None = None,
    shell: bool = False,
    env: dict[str, str] | None = None,
    env_remove: list[str] | None = None,
) -> int:
    """Launch a process without waiting for it to complete.

    This is for fire-and-forget process launching where you need the PID
    but don't need to wait for completion or capture output.

    Environment variables are always inherited from the parent process
    via prepare_env(). The ``env`` parameter merges on top of the parent
    environment rather than replacing it entirely.

    Args:
        command: Command as list or string (string requires shell=True)
        cwd: Working directory for the process
        shell: Whether to execute through shell (required for string commands)
        env: Extra environment variables merged on top of the parent env
        env_remove: Environment variable names to remove after merging

    Returns:
        Process ID (PID) of the launched process

    Example:
        # Launch VSCode — parent env is inherited automatically
        pid = launch_process(["code", "myfile.txt"])

        # Launch with extra env vars (no need for os.environ.copy())
        pid = launch_process(["code", "myfile.txt"], env={"CUSTOM_VAR": "value"})
    """
    cwd_str = str(cwd) if cwd else None
    prepared_env = prepare_env(command, env, env_remove)

    process = subprocess.Popen(
        command,
        cwd=cwd_str,
        shell=shell,
        env=prepared_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return process.pid
