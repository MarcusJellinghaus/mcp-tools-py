"""Shared utility to read target directories from pyproject.toml.

Reads source and test directory paths from pyproject.toml configuration,
with sensible fallbacks when sections are missing.
"""

import dataclasses
import logging
import os
import tomllib
from typing import Literal

logger = logging.getLogger(__name__)

ToolName = Literal[
    "mypy",
    "pylint",
    "pytest",
    "ruff",
    "bandit",
    "vulture",
    "tach",
    "lint-imports",
    "black",
    "isort",
]

DEFAULT_CHECK_TIMEOUT = 120
DEFAULT_PYTEST_TIMEOUT = 300

_CONFIG_SECTION = "mcp-tools-py"
_SHARED_TIMEOUT_KEY = "check-timeout"


@dataclasses.dataclass
class TargetDirs:
    """Target directories resolved from pyproject.toml.

    Attributes:
        directories: Combined source + test dirs that exist on disk.
        warnings: Fallback warnings (empty if pyproject.toml had values).
    """

    directories: list[str]
    warnings: list[str]


def get_target_directories(project_dir: str) -> TargetDirs:
    """Read source and test directories from pyproject.toml.

    Parses ``[tool.setuptools.packages.find] where`` for source dirs
    and ``[tool.pytest.ini_options] testpaths`` for test dirs.  Falls back
    to ``["src"]`` / ``["tests"]`` respectively when sections are missing.

    Args:
        project_dir: Path to project root containing pyproject.toml.

    Returns:
        A ``TargetDirs`` with the directories that exist on disk and any
        fallback warnings.

    Raises:
        ValueError: If none of the resolved directories exist on disk.
    """
    warnings: list[str] = []
    pyproject_path = os.path.join(project_dir, "pyproject.toml")

    toml_data: dict[str, object] = {}
    if os.path.isfile(pyproject_path):
        with open(pyproject_path, "rb") as f:
            try:
                toml_data = tomllib.load(f)
            except tomllib.TOMLDecodeError as exc:
                raise ValueError(f"Invalid pyproject.toml: {exc}") from exc

    # --- source dirs ---
    src_dirs: list[str] | None = None
    try:
        tool = toml_data["tool"]
        assert isinstance(tool, dict)
        setuptools = tool["setuptools"]
        assert isinstance(setuptools, dict)
        packages = setuptools["packages"]
        assert isinstance(packages, dict)
        find = packages["find"]
        assert isinstance(find, dict)
        where = find["where"]
        assert isinstance(where, list)
        src_dirs = [str(d) for d in where]
    except (KeyError, AssertionError):
        src_dirs = None

    if src_dirs is None:
        src_dirs = ["src"]
        warnings.append(
            "Warning: [tool.setuptools.packages.find] where not found "
            "in pyproject.toml, defaulting to ['src']"
        )

    # --- test dirs ---
    test_dirs: list[str] | None = None
    try:
        tool = toml_data["tool"]
        assert isinstance(tool, dict)
        pytest_section = tool["pytest"]
        assert isinstance(pytest_section, dict)
        ini_options = pytest_section["ini_options"]
        assert isinstance(ini_options, dict)
        testpaths = ini_options["testpaths"]
        assert isinstance(testpaths, list)
        test_dirs = [str(d) for d in testpaths]
    except (KeyError, AssertionError):
        test_dirs = None

    if test_dirs is None:
        test_dirs = ["tests"]
        warnings.append(
            "Warning: [tool.pytest.ini_options] testpaths not found "
            "in pyproject.toml, defaulting to ['tests']"
        )

    # --- filter to existing dirs ---
    combined = src_dirs + test_dirs
    existing = [d for d in combined if os.path.isdir(os.path.join(project_dir, d))]

    if not existing:
        raise ValueError(f"No target directories found: {combined}")

    return TargetDirs(directories=existing, warnings=warnings)


def resolve_target_directories(
    project_dir: str,
    target_directories: list[str] | None,
) -> list[str] | str:
    """Resolve target directories, auto-detecting from pyproject.toml if needed.

    Args:
        project_dir: Path to project root.
        target_directories: Explicit directories, or None to auto-detect.

    Returns:
        A list of directory names on success, or an error message string on failure.
    """
    if target_directories is not None:
        return target_directories
    try:
        result = get_target_directories(project_dir)
        for warning in result.warnings:
            logger.warning(warning)
        return result.directories
    except ValueError as exc:
        return f"Error resolving target directories: {exc}"


def check_line_length_conflicts(
    project_dir: str,
    used_tools: list[str],
) -> list[str]:
    """Check for line-length mismatches across formatter configs in pyproject.toml.

    Compares ``line-length`` settings for black, isort, and ruff.  Tools not
    present in *used_tools* and without an explicit config entry are skipped.

    Args:
        project_dir: Path to project root containing pyproject.toml.
        used_tools: Tool names currently in use (e.g. ``["isort", "black"]``).

    Returns:
        A list of warning strings describing mismatches, or an empty list.
    """
    pyproject_path = os.path.join(project_dir, "pyproject.toml")

    toml_data: dict[str, object] = {}
    if os.path.isfile(pyproject_path):
        with open(pyproject_path, "rb") as f:
            try:
                toml_data = tomllib.load(f)
            except tomllib.TOMLDecodeError:
                return []

    tool_section = toml_data.get("tool")
    if not isinstance(tool_section, dict):
        tool_section = {}

    default_line_length = 88
    lengths: dict[str, int] = {}

    for tool in ("black", "isort", "ruff"):
        tool_cfg = tool_section.get(tool)
        if not isinstance(tool_cfg, dict):
            tool_cfg = {}

        # isort uses underscore: line_length
        key = "line_length" if tool == "isort" else "line-length"
        value = tool_cfg.get(key)

        if value is not None:
            lengths[tool] = int(value)
        elif tool in used_tools:
            lengths[tool] = default_line_length
        # else: skip — tool not configured and not in use

    if len(lengths) <= 1:
        return []

    unique_values = set(lengths.values())
    if len(unique_values) == 1:
        return []

    parts = ", ".join(f"{t}={v}" for t, v in sorted(lengths.items()))
    return [f"Line-length mismatch: {parts}. Formatting may be inconsistent."]


def validate_timeout(value: object, source: str) -> int:
    """Validate that *value* is a positive integer timeout.

    Args:
        value: The candidate timeout value.
        source: Human-readable origin of the value, used in the error message.

    Returns:
        The validated timeout in seconds.

    Raises:
        ValueError: If *value* is not a positive integer.  ``bool`` is
            rejected even though it is an ``int`` subclass.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{source} must be a positive integer, got {value!r}")
    if value <= 0:
        raise ValueError(f"{source} must be a positive integer, got {value}")
    return value


def _read_mcp_tools_section(project_dir: str) -> dict[str, object]:
    """Read the ``[tool.mcp-tools-py]`` table from pyproject.toml.

    Args:
        project_dir: Path to project root containing pyproject.toml.

    Returns:
        The section as a dict, or an empty dict when the file or section
        is missing or the section is not a table.

    Raises:
        ValueError: If pyproject.toml is not valid TOML.
    """
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if not os.path.isfile(pyproject_path):
        return {}

    with open(pyproject_path, "rb") as f:
        try:
            toml_data = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"Invalid pyproject.toml: {exc}") from exc

    tool_section = toml_data.get("tool")
    if not isinstance(tool_section, dict):
        return {}

    section = tool_section.get(_CONFIG_SECTION)
    return section if isinstance(section, dict) else {}


def get_check_timeout(
    project_dir: str,
    tool: ToolName,
    explicit: int | None = None,
    cli_timeout: int | None = None,
) -> int:
    """Resolve the subprocess timeout for one run of one program.

    Resolution order: *explicit* argument, ``[tool.mcp-tools-py]
    <tool>-timeout``, ``[tool.mcp-tools-py] check-timeout``, *cli_timeout*,
    then the built-in default (300 for pytest, 120 otherwise).

    Args:
        project_dir: Path to the project being checked.
        tool: Name of the program the timeout applies to.
        explicit: Per-call timeout supplied by the caller, if any.
        cli_timeout: Server-level ``--check-timeout`` value, if any.

    Returns:
        The resolved timeout in seconds.

    Raises:
        ValueError: If pyproject.toml is malformed, or any consulted value
            is not a positive integer.
    """
    if explicit is not None:
        return validate_timeout(explicit, "timeout_seconds")

    section = _read_mcp_tools_section(project_dir)
    for key in (f"{tool}-timeout", _SHARED_TIMEOUT_KEY):
        if key in section:
            return validate_timeout(section[key], f"[tool.{_CONFIG_SECTION}] {key}")

    if cli_timeout is not None:
        return validate_timeout(cli_timeout, "--check-timeout")

    return DEFAULT_PYTEST_TIMEOUT if tool == "pytest" else DEFAULT_CHECK_TIMEOUT
