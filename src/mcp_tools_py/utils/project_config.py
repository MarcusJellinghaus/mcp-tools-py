"""Shared utility to read target directories from pyproject.toml.

Reads source and test directory paths from pyproject.toml configuration,
with sensible fallbacks when sections are missing.
"""

import dataclasses
import logging
import os
import tomllib

logger = logging.getLogger(__name__)


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
