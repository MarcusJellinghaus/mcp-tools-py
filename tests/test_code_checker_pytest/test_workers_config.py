"""Tests for the pytest_workers loader and its verify data in workers.py."""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

import pytest

from mcp_tools_py.code_checker_pytest import workers
from mcp_tools_py.code_checker_pytest.workers import (
    VALID_VALUES_HINT,
    WorkersSetting,
    pytest_workers_verify,
    read_pytest_workers,
)

# Captured at import time, before the autouse fixture replaces it.
from mcp_tools_py.code_checker_pytest.workers import _config_path as real_config_path

UserConfig = Callable[[str], Path]
_WORKERS_LOGGER = "mcp_tools_py.code_checker_pytest.workers"


def _raise_runtime_error(*_args: object) -> NoReturn:
    raise RuntimeError("Could not determine home directory.")


def _warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        r
        for r in caplog.records
        if r.name == _WORKERS_LOGGER and r.levelno == logging.WARNING
    ]


class TestReadPytestWorkers:
    """read_pytest_workers() reads [mcp_tools_py] pytest_workers."""

    def test_missing_file_is_default_without_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger=_WORKERS_LOGGER)
        assert read_pytest_workers() == WorkersSetting("auto", False, None)
        assert not _warnings(caplog)

    @pytest.mark.parametrize(
        ("toml_value", "expected"),
        [
            ('"auto"', "auto"),
            ('"all"', "all"),
            ("0", 0),
            ("4", 4),
            ("64", 64),
        ],
    )
    def test_valid_values(
        self,
        user_config: UserConfig,
        caplog: pytest.LogCaptureFixture,
        toml_value: str,
        expected: str | int,
    ) -> None:
        caplog.set_level(logging.WARNING, logger=_WORKERS_LOGGER)
        user_config(f"[mcp_tools_py]\npytest_workers = {toml_value}\n")
        assert read_pytest_workers() == WorkersSetting(expected, True, None)
        assert not _warnings(caplog)

    @pytest.mark.parametrize(
        ("toml_value", "shown"),
        [
            ('"4"', '"4"'),
            ('"x"', '"x"'),
            ("true", "true"),
            ("-1", "-1"),
            ("1.5", "1.5"),
        ],
    )
    def test_invalid_values_fall_back_to_auto(
        self,
        user_config: UserConfig,
        caplog: pytest.LogCaptureFixture,
        toml_value: str,
        shown: str,
    ) -> None:
        caplog.set_level(logging.WARNING, logger=_WORKERS_LOGGER)
        user_config(f"[mcp_tools_py]\npytest_workers = {toml_value}\n")
        assert read_pytest_workers() == WorkersSetting(
            "auto", True, f"pytest_workers = {shown} in config.toml"
        )
        assert _warnings(caplog)

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "[other]\npytest_workers = 4\n",
            "[mcp_tools_py]\nother_key = 4\n",
            'mcp_tools_py = "not a table"\n',
            "mcp_tools_py = [1, 2]\n",
        ],
    )
    def test_section_or_key_missing_is_default(
        self, user_config: UserConfig, text: str
    ) -> None:
        user_config(text)
        assert read_pytest_workers() == WorkersSetting("auto", False, None)

    def test_invalid_toml(
        self, user_config: UserConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger=_WORKERS_LOGGER)
        user_config("[mcp_tools_py\npytest_workers = 4\n")
        assert read_pytest_workers() == WorkersSetting(
            "auto", True, "config.toml: invalid TOML"
        )
        assert _warnings(caplog)

    def test_non_utf8_file_is_invalid_toml(
        self, user_config: UserConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger=_WORKERS_LOGGER)
        path = user_config("")
        path.write_bytes(b'[mcp_tools_py]\nname = "\xff\xfe"\n')
        assert read_pytest_workers() == WorkersSetting(
            "auto", True, "config.toml: invalid TOML"
        )
        assert _warnings(caplog)

    def test_config_path_raising_is_unreadable(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger=_WORKERS_LOGGER)
        monkeypatch.setattr(workers, "_config_path", _raise_runtime_error)
        assert read_pytest_workers() == WorkersSetting(
            "auto", True, "config.toml: unreadable"
        )
        assert _warnings(caplog)

    def test_changed_file_is_read_again(self, user_config: UserConfig) -> None:
        user_config("[mcp_tools_py]\npytest_workers = 2\n")
        assert read_pytest_workers().value == 2
        user_config('[mcp_tools_py]\npytest_workers = "all"\n')
        assert read_pytest_workers().value == "all"


class TestRealConfigPath:
    """The real _config_path() goes through the shim, inside the guarded block."""

    def test_uses_user_app_data_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def fake_app_data_dir(app_name: str) -> Path:
            calls.append(app_name)
            return tmp_path

        monkeypatch.setattr(workers, "get_user_app_data_dir", fake_app_data_dir)
        assert real_config_path() == tmp_path / "config.toml"
        assert calls == ["mcp_coder"]

    def test_app_data_dir_raising_is_unreadable(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.WARNING, logger=_WORKERS_LOGGER)
        monkeypatch.setattr(workers, "_config_path", real_config_path)
        monkeypatch.setattr(workers, "get_user_app_data_dir", _raise_runtime_error)
        assert read_pytest_workers() == WorkersSetting(
            "auto", True, "config.toml: unreadable"
        )
        assert _warnings(caplog)


class TestPytestWorkersVerify:
    """pytest_workers_verify() returns (status, message, hint)."""

    def test_default(self) -> None:
        assert pytest_workers_verify() == ("ok", "auto (default)", None)

    def test_all_from_config(self, user_config: UserConfig) -> None:
        user_config('[mcp_tools_py]\npytest_workers = "all"\n')
        assert pytest_workers_verify() == ("ok", "all (config.toml)", None)

    def test_integer_from_config(self, user_config: UserConfig) -> None:
        user_config("[mcp_tools_py]\npytest_workers = 4\n")
        assert pytest_workers_verify() == ("ok", "4 (config.toml)", None)

    def test_invalid_value(self, user_config: UserConfig) -> None:
        user_config('[mcp_tools_py]\npytest_workers = "x"\n')
        assert pytest_workers_verify() == (
            "warning",
            'ignored pytest_workers = "x" in config.toml; using auto',
            VALID_VALUES_HINT,
        )

    def test_invalid_toml(self, user_config: UserConfig) -> None:
        user_config("[mcp_tools_py\n")
        assert pytest_workers_verify() == (
            "warning",
            "ignored config.toml: invalid TOML; using auto",
            "Fix or remove ~/.mcp_coder/config.toml.",
        )
