"""Runner for mypy type checking."""

import logging
import os
import tomllib
from datetime import datetime
from pathlib import Path

from mcp_tools_py.code_checker_mypy.models import MypyResult
from mcp_tools_py.code_checker_mypy.parsers import parse_mypy_json_output
from mcp_tools_py.log_utils import log_function_call
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.subprocess_runner import (
    check_tool_missing_error,
    execute_command,
    truncate_stderr,
)

logger = logging.getLogger(__name__)


def _expand_config_cache_dir(path: str) -> str:
    """Expand a ``cache_dir`` config value the way mypy does.

    ``config_parser.expand_path`` applies ``expandvars`` over ``expanduser``,
    and ``main.py`` then runs ``expanduser`` once more over the result.

    Args:
        path: The raw ``cache_dir`` value read from the config file.

    Returns:
        The expanded path.
    """
    return os.path.expanduser(os.path.expandvars(os.path.expanduser(path)))


def _resolve_cache_dir(
    project_dir: str, cache_dir: str | None
) -> tuple[str | None, bool]:
    """Resolve the cache directory mypy will use, and whether that is certain.

    Mypy takes the cache directory from, in order of precedence: the
    ``--cache-dir`` argument, the ``MYPY_CACHE_DIR`` environment variable, the
    ``cache_dir`` config setting, and the ``.mypy_cache`` default. Config is read
    from ``mypy.ini``, ``.mypy.ini``, ``pyproject.toml`` and ``setup.cfg`` in
    that order; only ``pyproject.toml`` is parsed here, so when an INI-format
    config could own the setting the answer is None rather than a guess. With no
    local config at all, mypy falls back to a user-level config that may set
    ``cache_dir``, so ``.mypy_cache`` is returned as an assumption.

    Path expansion follows mypy, which treats each source differently: a config
    value gets ``expandvars`` and ``expanduser``, ``MYPY_CACHE_DIR`` gets
    ``expanduser`` only, and a ``--cache-dir`` argument gets neither, because
    mypy parses the command line after its expansion pass.

    Args:
        project_dir: Path to the project directory, which is mypy's cwd.
        cache_dir: Cache directory passed on the command line, if any.

    Returns:
        A ``(path, certain)`` pair. ``path`` is None when nothing can be said;
        ``certain`` is False when the path is mypy's default rather than a
        resolved setting.
    """
    if cache_dir:
        return os.path.join(project_dir, cache_dir), True

    # The environment beats any config file, and run_mypy_check passes our own
    # environment through to mypy
    env_cache_dir = os.environ.get("MYPY_CACHE_DIR", "")
    if env_cache_dir.strip():
        return os.path.join(project_dir, os.path.expanduser(env_cache_dir)), True

    for ini_name in ("mypy.ini", ".mypy.ini"):
        if os.path.isfile(os.path.join(project_dir, ini_name)):
            return None, False

    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        try:
            with open(pyproject_path, "rb") as f:
                toml_data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            return None, False
        tool_section = toml_data.get("tool")
        mypy_section = (
            tool_section.get("mypy") if isinstance(tool_section, dict) else None
        )
        if isinstance(mypy_section, dict):
            configured = mypy_section.get("cache_dir", ".mypy_cache")
            if not isinstance(configured, str):
                return None, False
            return (
                os.path.join(project_dir, _expand_config_cache_dir(configured)),
                True,
            )

    if os.path.isfile(os.path.join(project_dir, "setup.cfg")):
        return None, False

    return os.path.join(project_dir, ".mypy_cache"), False


def _describe_cache(cache_path: str) -> str:
    """Describe a mypy cache directory: existence, total bytes, newest mtime.

    Args:
        cache_path: Path to the cache directory.

    Returns:
        A single line of facts about the directory.
    """
    if not os.path.isdir(cache_path):
        return f"{cache_path} (does not exist)"

    stats: list[os.stat_result] = []
    skipped = 0
    try:
        for entry in Path(cache_path).rglob("*"):
            # A killed mypy can leave the cache mid-write, so an entry may
            # vanish or be unreadable -- skip it, not the whole report
            try:
                if entry.is_file():
                    stats.append(entry.stat())
            except OSError:
                skipped += 1
    except OSError as exc:
        if not stats:
            return f"{cache_path} (unreadable: {exc})"
        skipped += 1  # the walk stopped early; report what was counted

    if not stats:
        return f"{cache_path} (empty)"

    total_bytes = sum(s.st_size for s in stats)
    newest = datetime.fromtimestamp(max(s.st_mtime for s in stats)).isoformat()
    skipped_note = f", {skipped} skipped" if skipped else ""
    return (
        f"{cache_path} ({total_bytes} bytes across {len(stats)} files"
        f"{skipped_note}, newest {newest})"
    )


@log_function_call
def run_mypy_check(
    project_dir: str,
    python_executable: str,
    disable_error_codes: list[str] | None = None,
    target_directories: list[str] | None = None,
    follow_imports: str | None = None,
    cache_dir: str | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
) -> MypyResult:
    """Run mypy type checking on project.

    Args:
        project_dir: Path to the project directory
        disable_error_codes: List of error codes to ignore (e.g., ['import', 'arg-type'])
        target_directories: Directories to check (auto-detected from pyproject.toml when None)
        follow_imports: How to handle imports ('normal', 'silent', 'skip', 'error');
            omitted from the command line when None
        python_executable: Python interpreter to use (default: sys.executable)
        cache_dir: Custom cache directory for incremental checking
        timeout_seconds: Maximum seconds to wait for mypy

    Returns:
        MypyResult with execution results

    Raises:
        FileNotFoundError: If `project_dir` does not exist.
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
    ]

    # Add cache directory
    if cache_dir:
        command.extend(["--cache-dir", cache_dir])

    # Add follow imports setting only when asked: it is cache-affecting, and
    # otherwise the project's [tool.mypy] decides
    if follow_imports:
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
            "targets": mypy_targets,
            "command": " ".join(command),
        },
    )

    # MYPY_NUM_WORKERS forces mypy's native parser and is cache-affecting, so an
    # ambient value would silently split the cache
    env = os.environ.copy()
    env.pop("MYPY_NUM_WORKERS", None)

    # Execute mypy
    result = execute_command(
        command=command, cwd=project_dir, timeout_seconds=timeout_seconds, env=env
    )

    # Check for missing mypy module early (before other error handling)
    stderr = result.stderr or ""
    tool_error = check_tool_missing_error(stderr, "mypy", python_executable)
    if tool_error:
        return MypyResult(return_code=result.return_code, messages=[], error=tool_error)

    # Report a timeout as a timeout: execute_command sets execution_error too
    if result.timed_out:
        cache_path, cache_certain = _resolve_cache_dir(project_dir, cache_dir)
        if cache_path is None:
            cache_line = "Cache: the cache directory could not be resolved."
        elif cache_certain:
            cache_line = f"Cache: {_describe_cache(cache_path)}"
        else:
            cache_line = (
                f"Cache (assumed, mypy's default location): "
                f"{_describe_cache(cache_path)}"
            )
        return MypyResult(
            return_code=1,
            messages=[],
            error="\n".join(
                [
                    f"timed out after {timeout_seconds} seconds",
                    cache_line,
                    "A killed run leaves a partial cache; comparing size and mtime "
                    "across runs shows whether successive runs make progress.",
                    f"Command: {' '.join(command)}",
                    f"cwd: {project_dir}",
                    f"interpreter: {python_executable}",
                    "A cold mypy cache on a large project can take longer than "
                    "the limit.",
                    f"Retry with a larger timeout_seconds "
                    f"(this run used {timeout_seconds}).",
                ]
            ),
        )

    # Handle execution errors
    if result.execution_error:
        error_msg = result.execution_error
        if stderr.strip():
            error_msg += f" stderr: {truncate_stderr(stderr.strip())}"
        return MypyResult(return_code=result.return_code, messages=[], error=error_msg)

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
