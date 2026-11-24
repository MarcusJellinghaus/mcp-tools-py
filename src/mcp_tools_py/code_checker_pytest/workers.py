"""Size pytest-xdist's `-n auto` from [mcp_tools_py] pytest_workers in ~/.mcp_coder/config.toml."""

import json
import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from mcp_tools_py.utils.user_app_data import get_user_app_data_dir

logger = logging.getLogger(__name__)

ENV_KEY = "PYTEST_XDIST_AUTO_NUM_WORKERS"
_SECTION, _KEY = "mcp_tools_py", "pytest_workers"
VALID_VALUES_HINT = 'Valid values: "auto", "all", or an integer >= 0 (0 = serial).'
_CONFIG_FILE_HINT = "Fix or remove ~/.mcp_coder/config.toml."


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
