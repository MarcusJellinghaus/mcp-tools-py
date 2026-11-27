"""Shared utility to read target directories from pyproject.toml.

Reads source and test directory paths from pyproject.toml configuration,
with sensible fallbacks when sections are missing.
"""

import dataclasses
import glob
import logging
import os
import tomllib
from pathlib import Path, PurePath
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
    "deptry",
]

TargetTool = Literal["formatter", "ruff", "pylint", "mypy", "vulture", "bandit"]

DEFAULT_CHECK_TIMEOUT = 120
DEFAULT_PYTEST_TIMEOUT = 300

_CONFIG_SECTION = "mcp-tools-py"
_SHARED_TIMEOUT_KEY = "check-timeout"
_SCRIPT_DIRS_KEY = "script-directories"
_SCRIPT_TOOLS: frozenset[TargetTool] = frozenset(
    {"formatter", "ruff", "pylint", "mypy"}
)


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
    toml_data = _load_pyproject(project_dir)
    src_dirs = _read_source_dirs(toml_data, warnings)
    test_dirs = _read_test_dirs(toml_data, warnings)

    # --- filter to existing dirs ---
    combined = src_dirs + test_dirs
    existing = [d for d in combined if os.path.isdir(os.path.join(project_dir, d))]

    if not existing:
        raise ValueError(f"No target directories found: {combined}")

    return TargetDirs(directories=existing, warnings=warnings)


def _read_source_dirs(toml_data: dict[str, object], warnings: list[str]) -> list[str]:
    """Read ``[tool.setuptools.packages.find] where``, defaulting to ``["src"]``.

    Args:
        toml_data: Parsed pyproject.toml data.
        warnings: List to append a fallback warning to.

    Returns:
        The configured source directories, or ``["src"]``.
    """
    src_dirs: list[str] | None = None
    try:
        tool = toml_data["tool"]
        assert isinstance(tool, dict)  # noqa: S101
        setuptools = tool["setuptools"]
        assert isinstance(setuptools, dict)  # noqa: S101
        packages = setuptools["packages"]
        assert isinstance(packages, dict)  # noqa: S101
        find = packages["find"]
        assert isinstance(find, dict)  # noqa: S101
        where = find["where"]
        assert isinstance(where, list)  # noqa: S101
        src_dirs = [str(d) for d in where]
    except (KeyError, AssertionError):
        src_dirs = None

    if src_dirs is None:
        src_dirs = ["src"]
        warnings.append(
            "Warning: [tool.setuptools.packages.find] where not found "
            "in pyproject.toml, defaulting to ['src']"
        )
    return src_dirs


def _read_test_dirs(toml_data: dict[str, object], warnings: list[str]) -> list[str]:
    """Read ``[tool.pytest.ini_options] testpaths``, defaulting to ``["tests"]``.

    Args:
        toml_data: Parsed pyproject.toml data.
        warnings: List to append a fallback warning to.

    Returns:
        The configured test directories, or ``["tests"]``.
    """
    test_dirs: list[str] | None = None
    try:
        tool = toml_data["tool"]
        assert isinstance(tool, dict)  # noqa: S101
        pytest_section = tool["pytest"]
        assert isinstance(pytest_section, dict)  # noqa: S101
        ini_options = pytest_section["ini_options"]
        assert isinstance(ini_options, dict)  # noqa: S101
        testpaths = ini_options["testpaths"]
        assert isinstance(testpaths, list)  # noqa: S101
        test_dirs = [str(d) for d in testpaths]
    except (KeyError, AssertionError):
        test_dirs = None

    if test_dirs is None:
        test_dirs = ["tests"]
        warnings.append(
            "Warning: [tool.pytest.ini_options] testpaths not found "
            "in pyproject.toml, defaulting to ['tests']"
        )
    return test_dirs


def get_test_directories(project_dir: str) -> list[str]:
    """Read the test directories from pyproject.toml, on disk or not.

    Args:
        project_dir: Path to project root containing pyproject.toml.

    Returns:
        ``[tool.pytest.ini_options] testpaths``, or ``["tests"]`` when missing.
        A ``ValueError`` from :func:`_load_pyproject` propagates when
        pyproject.toml is not valid TOML.
    """
    return _read_test_dirs(_load_pyproject(project_dir), [])


def resolve_test_paths(
    project_dir: str, test_folder: str | None
) -> tuple[list[str], str | None]:
    """Choose the test paths to pass to pytest.

    An explicit *test_folder* wins and pyproject.toml is not read.  Otherwise
    the non-empty ``[tool.pytest.ini_options] testpaths`` entries are expanded
    as globs and those that exist are used.  When ``testpaths`` is unset, empty
    or not a list, or no entry exists, ``tests`` is used.

    Args:
        project_dir: Path to project root containing pyproject.toml.
        test_folder: Explicit test folder, or None to resolve from pyproject.toml.

    Returns:
        ``(paths, note)``: a non-empty list of paths relative to *project_dir*,
        and a note when ``testpaths`` is set but no entry exists, else None.
        A ``ValueError`` from :func:`_load_pyproject` propagates when
        pyproject.toml is not valid TOML.
    """
    if test_folder is not None:
        return [test_folder], None
    warnings: list[str] = []
    entries = _read_test_dirs(_load_pyproject(project_dir), warnings)
    if warnings or not entries:
        return ["tests"], None
    paths = [
        path
        for entry in entries
        for path in sorted(glob.iglob(entry, root_dir=project_dir, recursive=True))
    ]
    if paths:
        return paths, None
    return [
        "tests"
    ], f"testpaths entries not found: {entries}; falling back to 'tests'."


def resolve_target_directories(
    project_dir: str,
    target_directories: list[str] | None,
    tool: TargetTool,
) -> list[str] | str:
    """Resolve target directories, auto-detecting from pyproject.toml if needed.

    An explicit *target_directories* is returned as given and pyproject.toml
    is not read.  Otherwise the source (``[tool.setuptools.packages.find]
    where``) and test (``[tool.pytest.ini_options] testpaths``) folders that
    exist on disk are used, followed, for the formatter, ruff, pylint and
    mypy, by the ``[tool.mcp-tools-py] script-directories`` folders.  The
    key is validated for every *tool*, so an invalid value is reported even
    by tools that add no scripts.

    Args:
        project_dir: Path to project root.
        target_directories: Explicit directories, or None to auto-detect.
        tool: The program the directories are for.

    Returns:
        A list of directory names (source, tests, scripts) on success, or an
        error message string on failure.  Never raises.
    """
    if target_directories is not None:
        return target_directories
    try:
        toml_data = _load_pyproject(project_dir)
        warnings: list[str] = []
        auto = _read_source_dirs(toml_data, warnings) + _read_test_dirs(
            toml_data, warnings
        )
        existing = [d for d in auto if os.path.isdir(os.path.join(project_dir, d))]
        scripts = _read_script_dirs(toml_data, project_dir, existing)
    except ValueError as exc:
        return f"Error resolving target directories: {exc}"
    for warning in warnings:
        logger.warning(warning)
    dirs = existing + (scripts if tool in _SCRIPT_TOOLS else [])
    if dirs:
        return dirs
    return f"Error resolving target directories: No target directories found: {auto}"


def _path_key(entry: str) -> tuple[str, ...]:
    """Lexical comparison key: case- and separator-insensitive where the OS is.

    Returns:
        The path parts of *entry* after ``os.path.normcase``; ``()`` for ``.``.
    """
    return PurePath(os.path.normcase(entry)).parts


def _overlaps(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    """Compare two path keys from :func:`_path_key`.

    Returns:
        True when either key is a prefix of, or equal to, the other.
    """
    return a[: len(b)] == b or b[: len(a)] == a


def _read_script_dirs(
    toml_data: dict[str, object], project_dir: str, auto_dirs: list[str]
) -> list[str]:
    """Validated, normalised ``[tool.mcp-tools-py] script-directories`` entries.

    Args:
        toml_data: Parsed pyproject.toml data.
        project_dir: Path to project root; entries must be folders inside it.
        auto_dirs: Source and test folders on disk; no entry may overlap one.

    Returns:
        The entries in POSIX form (``./tools/`` gives ``tools``); ``[]`` when
        the key is missing or empty.

    Raises:
        ValueError: on the first invalid entry; the message starts with the key.
    """
    label = f"[tool.{_CONFIG_SECTION}] {_SCRIPT_DIRS_KEY}"
    value = _mcp_tools_section(toml_data).get(_SCRIPT_DIRS_KEY, [])
    if not isinstance(value, list) or not all(isinstance(e, str) for e in value):
        raise ValueError(f"{label}: must be a list of folder names, got {value!r}")

    auto_keys = [(auto, _path_key(auto)) for auto in auto_dirs]
    seen: list[tuple[str, tuple[str, ...]]] = []
    for entry in value:
        path = PurePath(entry)
        if path.drive or path.root or ".." in path.parts or not path.parts:
            raise ValueError(
                f"{label}: entry {entry!r} must be a folder inside the project, "
                "relative to its root"
            )
        if not os.path.isdir(os.path.join(project_dir, entry)):
            raise ValueError(f"{label}: folder {entry!r} not found")
        key = _path_key(entry)
        for earlier, earlier_key in seen:
            if _overlaps(key, earlier_key):
                raise ValueError(f"{label}: folders {earlier!r} and {entry!r} overlap")
        for auto, auto_key in auto_keys:
            if _overlaps(key, auto_key):
                covers = (
                    f"; {auto!r} already covers it"
                    if key[: len(auto_key)] == auto_key
                    else ""
                )
                raise ValueError(
                    f"{label}: folder {entry!r} overlaps source/test folder "
                    f"{auto!r}{covers}"
                )
        seen.append((entry, key))
    return [PurePath(entry).as_posix() for entry in value]


def _resolve_source_dirs(
    project_dir: str, explicit: list[str] | None, label: str, arg_name: str
) -> list[str] | str:
    """Resolve source directories that exist on disk and contain no test path.

    Args:
        project_dir: Path to project root.
        explicit: Explicit directories, or None to auto-detect.
        label: What is being resolved, used in error messages.
        arg_name: Argument name the error tells the caller to pass.

    Returns:
        *explicit* as-is when given; otherwise the source directories from
        pyproject.toml that exist on disk and contain no test path.  An error
        message string naming *arg_name* when none remain.
    """
    if explicit is not None:
        return explicit
    try:
        toml_data = _load_pyproject(project_dir)
    except ValueError as exc:
        return f"Error resolving {label}: {exc}"

    warnings: list[str] = []
    src_dirs = _read_source_dirs(toml_data, warnings)
    test_dirs = _read_test_dirs(toml_data, warnings)
    for warning in warnings:
        logger.warning(warning)

    root = Path(project_dir)
    test_paths = [(root / t).resolve() for t in test_dirs]
    keep = [
        s
        for s in src_dirs
        if (root / s).is_dir()
        and not any(t.is_relative_to((root / s).resolve()) for t in test_paths)
    ]
    if keep:
        return keep
    return (
        f"Error resolving {label}: no source directory outside the test "
        f"paths (source: {src_dirs}, tests: {test_dirs}). "
        f"Pass {arg_name} explicitly."
    )


def resolve_source_directories(
    project_dir: str, target_directories: list[str] | None
) -> list[str] | str:
    """Resolve the source directories, excluding test paths.

    Args:
        project_dir: Path to project root.
        target_directories: Explicit directories, or None to auto-detect.

    Returns:
        *target_directories* as-is when given; otherwise the source directories
        from pyproject.toml that exist on disk and contain no test path.  An
        error message string naming ``target_directories`` when none remain.
    """
    return _resolve_source_dirs(
        project_dir, target_directories, "source directories", "target_directories"
    )


def resolve_coverage_source(
    project_dir: str, coverage_source: list[str] | None
) -> list[str] | str:
    """Resolve the directories to measure coverage for.

    Args:
        project_dir: Path to project root.
        coverage_source: Explicit directories, or None to auto-detect.

    Returns:
        *coverage_source* as-is when given; otherwise the source directories
        from pyproject.toml that exist on disk and contain no test path.  An
        error message string naming ``coverage_source`` when none remain.
    """
    return _resolve_source_dirs(
        project_dir, coverage_source, "coverage source", "coverage_source"
    )


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


def read_pyproject_tool_tables(project_root: Path) -> dict[str, object]:
    """The ``[tool]`` table of ``project_root/pyproject.toml``, empty when absent.

    Args:
        project_root: Path to project root containing pyproject.toml.

    Returns:
        The ``[tool]`` table as a dict, or an empty dict when the file is
        missing or has no ``[tool]`` table.  A ``ValueError`` from
        :func:`_load_pyproject` propagates when pyproject.toml is not valid
        TOML.
    """
    return _tool_tables(_load_pyproject(str(project_root)))


def _tool_tables(toml_data: dict[str, object]) -> dict[str, object]:
    """The ``[tool]`` table of parsed pyproject.toml data.

    Args:
        toml_data: Parsed pyproject.toml data.

    Returns:
        The table as a dict, or an empty dict when it is missing or not a table.
    """
    tool_section = toml_data.get("tool")
    return tool_section if isinstance(tool_section, dict) else {}


def _mcp_tools_section(toml_data: dict[str, object]) -> dict[str, object]:
    """The ``[tool.mcp-tools-py]`` table of parsed pyproject.toml data.

    Args:
        toml_data: Parsed pyproject.toml data.

    Returns:
        The table as a dict, or an empty dict when it or ``[tool]`` is
        missing or not a table.
    """
    section = _tool_tables(toml_data).get(_CONFIG_SECTION)
    return section if isinstance(section, dict) else {}


def _read_mcp_tools_section(project_dir: str) -> dict[str, object]:
    """Read the ``[tool.mcp-tools-py]`` table from pyproject.toml.

    Args:
        project_dir: Path to project root containing pyproject.toml.

    Returns:
        The section as a dict, or an empty dict when the file or section
        is missing or the section is not a table.  A ``ValueError`` from
        :func:`_load_pyproject` propagates on invalid TOML.
    """
    return _mcp_tools_section(_load_pyproject(project_dir))


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
        The resolved timeout in seconds.  A ``ValueError`` from
        :func:`_read_mcp_tools_section` or :func:`validate_timeout` propagates
        when pyproject.toml is malformed or a consulted value is not a
        positive integer.
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


def _load_pyproject(project_dir: str) -> dict[str, object]:
    """Load pyproject.toml from *project_dir*.

    Args:
        project_dir: Path to project root containing pyproject.toml.

    Returns:
        The parsed TOML data, or an empty dict when the file is missing.

    Raises:
        ValueError: If pyproject.toml is not valid TOML.
    """
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if not os.path.isfile(pyproject_path):
        return {}

    with open(pyproject_path, "rb") as f:
        try:
            return tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise ValueError(f"Invalid pyproject.toml: {exc}") from exc
