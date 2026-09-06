"""What one target Python environment reports about itself, probed once.

Layer 2 of the environment model: the questions that are fixed for a whole
server run — Python version, which modules are importable, which
distributions are installed.  One subprocess answers all of them, and the
answer is cached per interpreter path.
"""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Mapping, Optional

from mcp_tools_py.utils.subprocess_runner import execute_command

# Timeout for the one-shot environment probe.
PROBE_TIMEOUT_SECONDS = 30

# How much of the child's stderr to quote back in a failure message.
_STDERR_SNIPPET = 500

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
        detail = result.execution_error or result.stderr.strip()[:_STDERR_SNIPPET]
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
    return info
