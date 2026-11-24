"""Size pytest-xdist's `-n auto` from [mcp_tools_py] pytest_workers in ~/.mcp_coder/config.toml."""

import ctypes
import json
import logging
import os
import sys
import time
import tomllib
from dataclasses import dataclass
from fractions import Fraction
from itertools import pairwise
from pathlib import Path
from typing import Literal

from mcp_tools_py.code_checker_pytest.pytest_config import (
    EffectiveConfig,
    OptionValue,
)
from mcp_tools_py.utils.user_app_data import get_user_app_data_dir

logger = logging.getLogger(__name__)

ENV_KEY = "PYTEST_XDIST_AUTO_NUM_WORKERS"
_SECTION, _KEY = "mcp_tools_py", "pytest_workers"
VALID_VALUES_HINT = 'Valid values: "auto", "all", or an integer >= 0 (0 = serial).'
_CONFIG_FILE_HINT = "Fix or remove ~/.mcp_coder/config.toml."
_SAMPLES = 5
_AUTO_VALUES = ("auto", "logical")
_AUTO_ONLY = "pytest_workers applies to -n auto only"
_XDIST_DEFAULT = "xdist default"
# How a numeric -n's source is named on the workers: line; others as they are.
_SOURCE_LABELS = {"pyproject.toml": "pyproject.toml addopts", "-o": "-o addopts"}

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


@dataclass(frozen=True)
class WorkersPlan:
    """How one pytest run is sized.

    Attributes:
        env: The env vars to pass to run_tests: the caller's dict unchanged,
            or a copy with ``ENV_KEY`` set.
        serial: The resolved or pre-set worker count is 0.
        note: The ``workers: ...`` line, or None.
    """

    env: dict[str, str] | None
    serial: bool
    note: str | None


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
    if sys.platform == "win32":
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
    else:  # not a trailing return: mypy flags that unreachable on win32
        return None


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


def _is_env_key(key: str) -> bool:
    """Whether *key* names ``ENV_KEY``; case-insensitively on Windows.

    Args:
        key: An env var name from the caller.

    Returns:
        True when the subprocess would see it as ``ENV_KEY``.
    """
    return key == ENV_KEY or (os.name == "nt" and key.upper() == ENV_KEY)


def _preset(env_vars: dict[str, str] | None) -> str:
    """The run's pre-set ``ENV_KEY``: the caller's value wins over the server's.

    Args:
        env_vars: The caller's env vars, if any.

    Returns:
        The caller's last matching value, else the server's; ``""`` when unset.
    """
    value = os.environ.get(ENV_KEY, "")
    for key, env_value in (env_vars or {}).items():
        if _is_env_key(key):
            value = env_value
    return value


def _with_count(env_vars: dict[str, str] | None, count: int) -> dict[str, str]:
    """A copy of *env_vars* with ``ENV_KEY`` set to *count*, in one spelling.

    Args:
        env_vars: The caller's env vars, if any; never mutated.
        count: The worker count.

    Returns:
        The caller's other keys plus ``ENV_KEY``.
    """
    env = {k: v for k, v in (env_vars or {}).items() if not _is_env_key(k)}
    env[ENV_KEY] = str(count)
    return env


def _shown(count: int) -> str:
    """How a worker count is shown on the workers: line.

    Args:
        count: The worker count.

    Returns:
        ``serial`` for 0, else the number.
    """
    return "serial" if count == 0 else str(count)


def _line(setting: WorkersSetting, shown: str, *reasons: str) -> str:
    """Render the ``workers:`` line, with the setting's problem appended.

    Args:
        setting: The pytest_workers setting.
        shown: What the run uses, e.g. ``3``, ``serial`` or ``xdist default``.
        reasons: Why, in order.

    Returns:
        ``workers: <shown> (<reasons>[; ignored <problem>])``.
    """
    parts = [*reasons]
    if setting.problem:
        parts.append(f"ignored {setting.problem}")
    return f"workers: {shown} ({'; '.join(parts)})"


def _not_auto_note(n: OptionValue | None, setting: WorkersSetting) -> str | None:
    """The line for a run without ``-n auto``: only when the config is set.

    Args:
        n: The effective ``-n``, if any; not ``auto`` / ``logical``.
        setting: The pytest_workers setting.

    Returns:
        The line explaining that pytest_workers does not apply, or None.
    """
    if not setting.in_config:
        return None
    if n is None:
        return _line(setting, "no -n", _AUTO_ONLY)
    shown = "serial" if n.value == "0" else n.value
    source = _SOURCE_LABELS.get(n.source, n.source)
    return _line(setting, shown, f"-n {n.value} from {source}", _AUTO_ONLY)


def _preset_plan(
    preset: str, setting: WorkersSetting, env_vars: dict[str, str] | None
) -> WorkersPlan:
    """The plan when ``ENV_KEY`` is already set: xdist reads it as it is.

    Args:
        preset: The non-empty pre-set value.
        setting: The pytest_workers setting.
        env_vars: The caller's env vars, passed on unchanged.

    Returns:
        The plan reporting the pre-set value.
    """
    try:
        count = int(preset)
    except ValueError:
        reason = f'{ENV_KEY}="{preset}" is not an integer'
        return WorkersPlan(env_vars, False, _line(setting, _XDIST_DEFAULT, reason))
    return WorkersPlan(env_vars, count == 0, _line(setting, _shown(count), ENV_KEY))


def _auto_count(setting: WorkersSetting) -> tuple[int | None, str]:
    """The worker count for ``-n auto`` from the setting, sampling on Windows.

    Args:
        setting: The pytest_workers setting.

    Returns:
        ``(count, reason)``; count is None when xdist's default applies.
    """
    if setting.value == "all":
        return None, "all, config.toml"
    if isinstance(setting.value, int):
        return setting.value, "config.toml"
    if not _is_windows():
        return None, "auto, not Windows"
    idle, logical = sample_idle(), os.cpu_count()
    if idle is None or logical is None:
        return None, "auto, Windows, CPU load unavailable"
    load = round(100 * (1 - idle))
    return workers_for(logical, idle), f"auto, Windows, CPU load {load} %"


def resolve_workers(
    effective: EffectiveConfig, env_vars: dict[str, str] | None
) -> WorkersPlan:
    """Decide what ``-n auto`` means for one run; never raises.

    The command line is never changed: a count reaches xdist through
    ``ENV_KEY`` in a copy of *env_vars*. A value the caller or the server
    already set wins and skips sampling.

    Args:
        effective: The effective config of the call.
        env_vars: The caller's env vars, if any; never mutated.

    Returns:
        The env for run_tests, whether the run is serial, and the line.
    """
    setting = read_pytest_workers()
    n = effective.n
    if n is None or n.value not in _AUTO_VALUES:
        return WorkersPlan(env_vars, False, _not_auto_note(n, setting))
    preset = _preset(env_vars)
    if preset:
        return _preset_plan(preset, setting, env_vars)
    count, reason = _auto_count(setting)
    if count is None:
        return WorkersPlan(env_vars, False, _line(setting, _XDIST_DEFAULT, reason))
    return WorkersPlan(
        _with_count(env_vars, count), count == 0, _line(setting, _shown(count), reason)
    )
