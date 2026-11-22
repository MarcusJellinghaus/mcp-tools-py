"""Read the project's pytest config from pyproject.toml, in pytest's file order."""

import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from mcp_tools_py.utils.file_utils import read_file
from mcp_tools_py.utils.project_config import read_pyproject_tool_tables

# pytest reads the first of these that exists, even when empty, before pyproject.toml.
DEDICATED_FILES = ("pytest.toml", ".pytest.toml", "pytest.ini", ".pytest.ini")

# Read by pytest only when pyproject.toml has no pytest section: file, section header.
_FALLBACK_FILES = (("tox.ini", "[pytest]"), ("setup.cfg", "[tool:pytest]"))

# pytest's bool spellings for ini values, compared lowercased.
_TRUE_SPELLINGS = frozenset({"y", "yes", "t", "true", "on", "1"})
_FALSE_SPELLINGS = frozenset({"n", "no", "f", "false", "off", "0"})


@dataclass(frozen=True)
class PytestConfig:
    """What pyproject.toml says about pytest, or which other file pytest reads instead.

    Attributes:
        addopts: ini ``addopts`` tokens; empty when none.
        markers: Project marker names, in config order.
        strict_markers: Table value of ``strict_markers``; None when unset or
            of a type the table does not accept.
        strict: Table value of ``strict``; None when unset or of a type the
            table does not accept.
        not_read: The file pytest reads instead of pyproject.toml; the fields
            above are then empty.
    """

    addopts: list[str]
    markers: list[str]
    strict_markers: bool | None
    strict: bool | None
    not_read: str | None = None


def _parse_bool(value: str) -> bool | None:
    """Parse one of pytest's bool spellings, case-insensitively.

    Args:
        value: The ini string value.

    Returns:
        The bool it spells, or None for any other text.
    """
    lowered = value.lower()
    if lowered in _TRUE_SPELLINGS:
        return True
    if lowered in _FALSE_SPELLINGS:
        return False
    return None


def _marker_name(entry: str) -> str:
    """Return the marker name of a ``markers`` entry: the text before ``(`` or ``:``."""
    for separator in "(:":
        entry = entry.split(separator, 1)[0]
    return entry.strip()


def _read_addopts(value: object, is_ini: bool) -> list[str]:
    """Return the ``addopts`` tokens of a string (ini_options only) or a list."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if is_ini and isinstance(value, str):
        try:
            return shlex.split(value)
        except ValueError:
            return []
    return []


def _read_markers(value: object, is_ini: bool) -> list[str]:
    """Return the marker names of a list or a multi-line string (ini only)."""
    if isinstance(value, list):
        entries = [str(v) for v in value]
    elif is_ini and isinstance(value, str):
        entries = value.splitlines()
    else:
        return []
    names = [_marker_name(entry) for entry in entries]
    return [name for name in names if name]


def _read_strict(value: object, is_ini: bool) -> bool | None:
    """Return a strict key's bool, or its bool spelling (ini_options only)."""
    if isinstance(value, bool):
        return value
    if is_ini and isinstance(value, str):
        return _parse_bool(value)
    return None


def _fallback_file(root: Path) -> str | None:
    """Find the ``tox.ini`` / ``setup.cfg`` that has a pytest section.

    Args:
        root: The project root.

    Returns:
        The file name, or None when neither has one.  An ``OSError`` from
        reading an existing file propagates.
    """
    for name, header in _FALLBACK_FILES:
        path = root / name
        if os.path.isfile(path) and any(
            line.strip() == header for line in read_file(path).splitlines()
        ):
            return name
    return None


def read_pytest_config(project_dir: str) -> PytestConfig | None:
    """Read the project's pytest config. Never raises; None when it can't be read.

    The dedicated pytest files win over pyproject.toml; ``tox.ini [pytest]`` and
    ``setup.cfg [tool:pytest]`` only when pyproject.toml has no pytest section
    (an ``ini_options`` table, even empty, or a non-empty ``[tool.pytest]``).

    Args:
        project_dir: Path to the project root.

    Returns:
        The config read from ``[tool.pytest.ini_options]`` or ``[tool.pytest]``,
        or one naming the file pytest reads instead in ``not_read``.  None when
        a file can't be read, pyproject.toml is not valid TOML, or both pytest
        tables are non-empty (pytest rejects that).
    """
    root = Path(project_dir)
    for name in DEDICATED_FILES:
        if os.path.isfile(root / name):
            return PytestConfig([], [], None, None, name)
    try:
        tool = read_pyproject_tool_tables(root)
        pytest_table = tool.get("pytest")
        if not isinstance(pytest_table, dict):
            pytest_table = {}
        ini = pytest_table.get("ini_options")
        if not isinstance(ini, dict):
            ini = None
        native = {k: v for k, v in pytest_table.items() if k != "ini_options"}
        if ini and native:
            return None
        if ini is None and not native:
            return PytestConfig([], [], None, None, _fallback_file(root))
    except (ValueError, OSError):
        return None

    # A non-empty [tool.pytest] wins over an empty ini_options.
    is_ini = not native
    table = native or ini or {}
    return PytestConfig(
        addopts=_read_addopts(table.get("addopts"), is_ini),
        markers=_read_markers(table.get("markers"), is_ini),
        strict_markers=_read_strict(table.get("strict_markers"), is_ini),
        strict=_read_strict(table.get("strict"), is_ini),
    )
