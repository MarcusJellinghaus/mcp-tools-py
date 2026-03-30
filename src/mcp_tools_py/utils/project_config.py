"""Shared utility to read target directories from pyproject.toml.

Reads source and test directory paths from pyproject.toml configuration,
with sensible fallbacks when sections are missing.
"""

import dataclasses
import os
import tomllib


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
            toml_data = tomllib.load(f)

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
