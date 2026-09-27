"""What one target Python environment reports about itself, probed once.

Layer 2 of the environment model: the questions that are fixed for a whole
server run — Python version, which modules are importable, which
distributions are installed.  One subprocess answers all of them, and the
answer is cached per interpreter path.

`locate_packages` is the exception: where a package lives can change while the
server runs, so it probes afresh on every call.
"""

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Optional

from mcp_tools_py.utils.subprocess_runner import execute_command

logger = logging.getLogger(__name__)

# Timeout for the one-shot environment probe.
PROBE_TIMEOUT_SECONDS = 30

# How much of a child process's stderr to quote back in a failure message.
STDERR_SNIPPET = 500

# Tool key -> module for `python -m <module>`, or None when the tool is only
# ever run through its console script. The console script is named after the key.
TOOL_MODULES: dict[str, Optional[str]] = {
    "pytest": "pytest",
    "pylint": "pylint",
    "mypy": "mypy",
    "black": "black",
    "isort": "isort",
    "lint-imports": None,
    "vulture": None,
    "ruff": None,
    "bandit": None,
    "tach": None,
}

# Tool key -> distribution to install, when it differs from the key.
TOOL_PACKAGES: dict[str, str] = {"lint-imports": "import-linter"}

# The modules the probe is asked about: every tool invoked as `python -m`.
PROBED_MODULES: tuple[str, ...] = tuple(m for m in TOOL_MODULES.values() if m)

# The distributions the `python -m` tools ship in, lowercased to match the blob.
# The console-script tools are deliberately absent: they come from the tool env,
# which this probe never describes.
TOOL_DISTRIBUTIONS: tuple[str, ...] = tuple(
    TOOL_PACKAGES.get(key, key).lower()
    for key, module in TOOL_MODULES.items()
    if module is not None
)


@dataclass(frozen=True)
class EnvironmentInfo:
    """What one Python interpreter reports about itself.

    Attributes:
        version: Python version of the interpreter, e.g. "3.11.9".
        sys_path: The interpreter's ``sys.path``.
        distributions: Lowercased distribution name -> installed version.
        importable: Module name -> whether the interpreter can import it.
        error: Why the probe could not be trusted, or None when it succeeded.
    """

    version: str
    sys_path: tuple[str, ...]
    distributions: Mapping[str, str]
    importable: Mapping[str, bool]
    error: Optional[str] = None


def probe_script_path() -> Path:
    """Locate the probe script on disk.

    Returns:
        Absolute path to ``target_scripts/probe.py``.  The script is run by
        path rather than by ``-m`` because ``mcp_tools_py`` is not installed
        in the target environment.
    """
    return Path(__file__).parent / "target_scripts" / "probe.py"


def locate_packages(
    interpreter: str, names: list[str]
) -> tuple[list[str], dict[str, list[str]]] | str:
    """Ask `interpreter` where each package in `names` lives.

    Args:
        interpreter: Path to the Python interpreter to ask.
        names: Package names to locate.

    Returns:
        `(usable, skipped)` — the directories to prepend to PYTHONPATH, in
        request order and without repeats; and, keyed by the package name they
        were found for, the located directories that are `interpreter`'s own
        site/purelib directories and must not be prepended.  Or a string
        saying why the probe could not be trusted.
    """
    if not names:
        return [], {}

    result = execute_command(
        [interpreter, str(probe_script_path()), "locate", *names],
        timeout_seconds=PROBE_TIMEOUT_SECONDS,
    )
    if result.timed_out:
        return f"probe of {interpreter} timed out after {PROBE_TIMEOUT_SECONDS} seconds"
    if result.execution_error or result.return_code != 0:
        detail = result.execution_error or result.stderr.strip()[:STDERR_SNIPPET]
        return f"could not locate {', '.join(names)} in {interpreter}: {detail}"

    located = _parse_locate_blob(result.stdout)
    if located is None:
        return f"probe of {interpreter} returned unparsable output"
    packages, site_dirs = located

    resolved_sites = [Path(site_dir).resolve() for site_dir in site_dirs]
    usable: list[str] = []
    skipped: dict[str, list[str]] = {}
    for name in names:
        for directory in packages.get(name, []):
            if _under_any(Path(directory).resolve(), resolved_sites):
                skipped.setdefault(name, []).append(directory)
            elif directory not in usable:
                usable.append(directory)
    return usable, skipped


def _parse_locate_blob(
    stdout: str,
) -> tuple[dict[str, list[str]], list[str]] | None:
    """Read a `probe.py locate` blob, rejecting anything of the wrong shape.

    Args:
        stdout: What the probe wrote.

    Returns:
        `(packages, site_dirs)`, or None when the blob cannot be trusted.
    """
    try:
        blob = json.loads(stdout)
        packages = blob["packages"]
        site_dirs = blob["site_dirs"]
    except (ValueError, KeyError, TypeError):
        return None
    if not (isinstance(packages, dict) and isinstance(site_dirs, list)):
        return None
    if not all(isinstance(site_dir, str) for site_dir in site_dirs):
        return None
    for name, directories in packages.items():
        if not (isinstance(name, str) and isinstance(directories, list)):
            return None
        if not all(isinstance(directory, str) for directory in directories):
            return None
    return packages, site_dirs


def _under_any(directory: Path, site_dirs: list[Path]) -> bool:
    """Report whether `directory` is, or sits inside, one of `site_dirs`.

    Args:
        directory: A resolved located directory.
        site_dirs: The interpreter's resolved site directories.

    Returns:
        True when the directory may not go on PYTHONPATH.
    """
    return any(directory.is_relative_to(site_dir) for site_dir in site_dirs)


def _failed(reason: str) -> EnvironmentInfo:
    """Build the fail-open result used when the probe cannot be trusted.

    Every probed module reads as importable, so a failed probe lets the call
    proceed and surface the real error instead of making all five module
    tools vanish at once.

    Args:
        reason: What went wrong, for the caller to log.

    Returns:
        A failure-shaped EnvironmentInfo with `error` set.
    """
    return EnvironmentInfo(
        version="",
        sys_path=(),
        distributions={},
        importable={module: True for module in PROBED_MODULES},
        error=reason,
    )


def _log_tool_versions(interpreter: str, info: EnvironmentInfo) -> None:
    """Report which tool distributions the probe found, and at which version.

    Args:
        interpreter: Path to the interpreter that was probed.
        info: The successful probe result to report on.
    """
    found = [
        f"{name} {info.distributions[name]}"
        for name in TOOL_DISTRIBUTIONS
        if name in info.distributions
    ]
    logger.info(
        "tool versions in %s: %s", interpreter, ", ".join(found) if found else "none"
    )


@lru_cache(maxsize=None)
def get_environment_info(interpreter: str) -> EnvironmentInfo:
    """Describe `interpreter`, running the probe at most once per path.

    Failures are returned rather than raised: `lru_cache` does not cache an
    exception, and a failed probe must be remembered like any other answer.

    Args:
        interpreter: Path to the Python interpreter to describe.

    Returns:
        The probe result, or a fail-open EnvironmentInfo whose `error` says
        why the probe could not be trusted.
    """
    result = execute_command(
        [interpreter, str(probe_script_path()), "info", *PROBED_MODULES],
        timeout_seconds=PROBE_TIMEOUT_SECONDS,
    )
    if result.timed_out:
        return _failed(
            f"probe of {interpreter} timed out after {PROBE_TIMEOUT_SECONDS} seconds"
        )
    if result.execution_error or result.return_code != 0:
        detail = result.execution_error or result.stderr.strip()[:STDERR_SNIPPET]
        return _failed(f"could not probe {interpreter}: {detail}")

    try:
        blob = json.loads(result.stdout)
        info = EnvironmentInfo(
            version=blob["version"],
            sys_path=tuple(blob["sys_path"]),
            distributions=blob["distributions"],
            importable=blob["importable"],
        )
    except (ValueError, KeyError, TypeError):
        return _failed(f"probe of {interpreter} returned unparsable output")
    _log_tool_versions(interpreter, info)
    return info
