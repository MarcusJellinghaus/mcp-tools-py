"""Tests for the -n auto sizing wired into check_code_with_pytest."""

import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.code_checker_pytest.models import PytestReport
from mcp_tools_py.code_checker_pytest.pytest_config import effective_config
from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_pytest.verdict import RunStatus
from mcp_tools_py.code_checker_pytest.workers import ENV_KEY

UserConfig = Callable[[str], Path]
_RUNNERS = "mcp_tools_py.code_checker_pytest.runners"
_ENV_VARS_INDEX = 6  # position of env_vars in run_tests' positional arguments


def _config(value: str) -> str:
    return f"[mcp_tools_py]\npytest_workers = {value}\n"


def _report() -> PytestReport:
    summary = MagicMock()
    summary.collected = summary.total = summary.passed = 1
    summary.failed = summary.error = summary.skipped = 0
    summary.xfailed = summary.xpassed = summary.deselected = 0
    return PytestReport(
        created=0.0,
        duration=0.1,
        exitcode=0,
        root="/p",
        environment={},
        summary=summary,
        tests=[],
    )


@pytest.fixture
def run_tests() -> Iterator[MagicMock]:
    """Patch run_tests in the runner module; it returns one passed test."""
    with patch(f"{_RUNNERS}.run_tests", return_value=_report()) as mocked:
        yield mocked


def _env_of(mocked: MagicMock) -> dict[str, str] | None:
    env: dict[str, str] | None = mocked.call_args.args[_ENV_VARS_INDEX]
    return env


def _check(project: Path, **kwargs: Any) -> dict[str, Any]:
    return check_code_with_pytest(
        str(project), python_executable=sys.executable, **kwargs
    )


def test_config_count_reaches_run_tests(
    tmp_path: Path, user_config: UserConfig, run_tests: MagicMock
) -> None:
    user_config(_config("4"))

    result = _check(tmp_path, extra_args=["-n", "auto"])

    assert result["workers_note"] == "workers: 4 (config.toml)"
    assert result["workers_serial"] is False
    env = _env_of(run_tests)
    assert env is not None
    assert env[ENV_KEY] == "4"


def test_config_is_reread_without_restart(
    tmp_path: Path, user_config: UserConfig, run_tests: MagicMock
) -> None:
    user_config(_config("4"))
    first = _check(tmp_path, extra_args=["-n", "auto"])
    user_config(_config("2"))
    second = _check(tmp_path, extra_args=["-n", "auto"])

    assert first["workers_note"] == "workers: 4 (config.toml)"
    assert second["workers_note"] == "workers: 2 (config.toml)"
    env = _env_of(run_tests)
    assert env is not None
    assert env[ENV_KEY] == "2"


def test_config_zero_is_serial(
    tmp_path: Path, user_config: UserConfig, run_tests: MagicMock
) -> None:
    user_config(_config("0"))

    result = _check(tmp_path, extra_args=["-n", "auto"])

    assert result["workers_serial"] is True
    assert result["workers_note"] == "workers: serial (config.toml)"
    env = _env_of(run_tests)
    assert env is not None
    assert env[ENV_KEY] == "0"


def test_error_return_carries_workers_keys(
    tmp_path: Path, user_config: UserConfig, run_tests: MagicMock
) -> None:
    user_config(_config("0"))
    run_tests.side_effect = RuntimeError("boom")

    result = _check(tmp_path, extra_args=["-n", "auto"])

    assert result["verdict"].status is RunStatus.ERROR
    assert result["workers_note"] == "workers: serial (config.toml)"
    assert result["workers_serial"] is True


def test_passed_effective_is_used_as_given(
    tmp_path: Path, user_config: UserConfig, run_tests: MagicMock
) -> None:
    user_config(_config("3"))
    effective = effective_config(str(tmp_path), None, ["-n", "auto"], None)

    with patch(f"{_RUNNERS}.effective_config") as computed:
        result = _check(tmp_path, effective=effective)

    computed.assert_not_called()
    assert result["workers_note"] == "workers: 3 (config.toml)"
    env = _env_of(run_tests)
    assert env is not None
    assert env[ENV_KEY] == "3"


def test_no_n_and_no_config_passes_env_through(
    tmp_path: Path, run_tests: MagicMock
) -> None:
    env_vars = {"A": "1"}

    result = _check(tmp_path, env_vars=env_vars)

    assert result["workers_note"] is None
    assert result["workers_serial"] is False
    assert _env_of(run_tests) is env_vars
