"""Size pytest-xdist's `-n auto` from [mcp_tools_py] pytest_workers in ~/.mcp_coder/config.toml."""

import ctypes
import json
import logging
import sys
import time
import tomllib
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Literal

from mcp_tools_py.utils.user_app_data import get_user_app_data_dir

logger = logging.getLogger(__name__)

ENV_KEY = "PYTEST_XDIST_AUTO_NUM_WORKERS"
_SECTION, _KEY = "mcp_tools_py", "pytest_workers"
VALID_VALUES_HINT = 'Valid values: "auto", "all", or an integer >= 0 (0 = serial).'
_CONFIG_FILE_HINT = "Fix or remove ~/.mcp_coder/config.toml."
_SAMPLES = 5

SystemTimes = tuple[int, int, int]
"""``(idle, kernel, user)`` in 100-ns units; kernel time includes idle time."""


@dataclass(frozen=True)
class WorkersSetting:
    """The pytest_workers setting as read from config.toml.

    Attributes:
        value: ``"auto"``, ``"all"`` or an integer >= 0; ``"auto"`` on fallback.
        in_config: The key is present, or config.toml is unreadable / invalid.
        problem: Text that follows ``ignored `` on the workers: line, or None.
    """

    value: str | int
    in_config: bool
    problem: str | None


def _config_path() -> Path:
    """Path of the user's config.toml, ``~/.mcp_coder/config.toml``.

    Returns:
        The config file path; it may not exist.
    """
    return get_user_app_data_dir("mcp_coder") / "config.toml"


def _is_valid(value: object) -> bool:
    """Whether *value* is ``"auto"``, ``"all"`` or an integer >= 0 (not a bool).

    Args:
        value: The raw TOML value.

    Returns:
        True when the value is accepted.
    """
    if isinstance(value, str):
        return value in ("auto", "all")
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def read_pytest_workers() -> WorkersSetting:
    """Read ``[mcp_tools_py] pytest_workers`` from config.toml; never raises.

    The file is read on every call. A missing file, section or key gives the
    default ``auto``. An unreadable or invalid file, or an invalid value, also
    gives ``auto``, with a warning logged and the problem recorded.

    Returns:
        The setting, its origin and any problem.
    """
    try:
        with open(_config_path(), "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        return WorkersSetting("auto", False, None)
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Ignoring config.toml: invalid TOML (%s)", exc)
        return WorkersSetting("auto", True, "config.toml: invalid TOML")
    except (OSError, RuntimeError) as exc:
        logger.warning("Ignoring config.toml: unreadable (%s)", exc)
        return WorkersSetting("auto", True, "config.toml: unreadable")

    section = data.get(_SECTION)
    if not isinstance(section, dict) or _KEY not in section:
        return WorkersSetting("auto", False, None)
    value = section[_KEY]
    if _is_valid(value):
        return WorkersSetting(value, True, None)
    problem = f"{_KEY} = {json.dumps(value, default=str)} in config.toml"
    logger.warning("Ignoring %s; using auto. %s", problem, VALID_VALUES_HINT)
    return WorkersSetting("auto", True, problem)


def pytest_workers_verify() -> tuple[Literal["ok", "warning"], str, str | None]:
    """Report the pytest_workers setting for verify(), without sampling the CPU.

    Returns:
        ``(status, message, hint)``: ``"ok"`` with the value and its source,
        or ``"warning"`` with the ignored problem and how to fix it.
    """
    setting = read_pytest_workers()
    if setting.problem is None:
        source = "config.toml" if setting.in_config else "default"
        return "ok", f"{setting.value} ({source})", None
    hint = VALID_VALUES_HINT if setting.problem.startswith(_KEY) else _CONFIG_FILE_HINT
    return "warning", f"ignored {setting.problem}; using auto", hint


def _is_windows() -> bool:
    """Whether sizing should sample the CPU: the single platform seam.

    Returns:
        True on Windows.
    """
    return sys.platform == "win32"


def _get_system_times() -> SystemTimes | None:
    """Read the system-wide CPU times through kernel32 ``GetSystemTimes``.

    Returns:
        ``(idle, kernel, user)`` in 100-ns units, or None when not on Windows
        or when the call fails.
    """
    if sys.platform != "win32":
        return None
    idle, kernel, user = (
        ctypes.c_ulonglong(),
        ctypes.c_ulonglong(),
        ctypes.c_ulonglong(),
    )
    try:
        ok = ctypes.windll.kernel32.GetSystemTimes(
            ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)
        )
    except (OSError, AttributeError, ctypes.ArgumentError) as exc:
        logger.debug("GetSystemTimes failed: %s", exc)
        return None
    if not ok:
        return None
    return idle.value, kernel.value, user.value


def idle_fraction(before: SystemTimes, after: SystemTimes) -> Fraction | None:
    """The exact idle share of CPU time between two readings.

    Args:
        before: The earlier reading.
        after: The later reading.

    Returns:
        Idle time over total time, or None when no time elapsed.
    """
    d_idle = after[0] - before[0]
    d_total = (after[1] - before[1]) + (after[2] - before[2])
    if d_total <= 0:
        return None
    return Fraction(d_idle, d_total)


def sample_idle(interval: float = 0.1) -> Fraction | None:
    """Sample the CPU idle share as the exact median of five intervals.

    Args:
        interval: Seconds to sleep between readings.

    Returns:
        The median idle fraction, or None when any reading or interval fails.
    """
    first = _get_system_times()
    if first is None:
        return None
    readings = [first]
    for _ in range(_SAMPLES):
        time.sleep(interval)
        reading = _get_system_times()
        if reading is None:
            return None
        readings.append(reading)
    fractions: list[Fraction] = []
    for before, after in pairwise(readings):
        fraction = idle_fraction(before, after)
        if fraction is None:
            return None
        fractions.append(fraction)
    return sorted(fractions)[_SAMPLES // 2]


def workers_for(logical: int, idle: Fraction) -> int:
    """Worker count for *logical* CPUs at idle share *idle*: half the idle CPUs.

    Args:
        logical: Number of logical CPUs.
        idle: Idle share of CPU time, between 0 and 1.

    Returns:
        ``floor(logical * idle / 2)``, or 0 (serial) when that is below 2.
    """
    n = (logical * idle.numerator) // (2 * idle.denominator)
    return n if n >= 2 else 0
