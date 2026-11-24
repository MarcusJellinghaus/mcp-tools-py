"""Tests for resolve_workers() and every workers: line format in workers.py."""

import os
from collections.abc import Callable
from fractions import Fraction
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mcp_tools_py.code_checker_pytest import workers
from mcp_tools_py.code_checker_pytest.pytest_config import (
    EffectiveConfig,
    effective_config,
)
from mcp_tools_py.code_checker_pytest.workers import (
    ENV_KEY,
    WorkersPlan,
    resolve_workers,
)

UserConfig = Callable[[str], Path]
SetIdle = Callable[[Fraction | None], MagicMock]
_CPU_COUNT = "mcp_tools_py.code_checker_pytest.workers.os.cpu_count"


def _effective(
    project: Path,
    extra_args: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
    addopts: str | None = None,
) -> EffectiveConfig:
    """Build the real effective config of a call on *project*."""
    if addopts is not None:
        (project / "pyproject.toml").write_text(
            f'[tool.pytest.ini_options]\naddopts = "{addopts}"\n', encoding="utf-8"
        )
    return effective_config(str(project), None, extra_args or [], env_vars)


def _config(value: str) -> str:
    return f"[mcp_tools_py]\npytest_workers = {value}\n"


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch) -> SetIdle:
    """Pretend to be Windows with 24 logical CPUs; the call sets the sampled idle."""
    monkeypatch.setattr(workers, "_is_windows", lambda: True)
    monkeypatch.setattr(_CPU_COUNT, lambda: 24)

    def set_idle(idle: Fraction | None) -> MagicMock:
        sampler = MagicMock(return_value=idle)
        monkeypatch.setattr(workers, "sample_idle", sampler)
        return sampler

    set_idle(Fraction(1, 2))
    return set_idle


class TestNoAutoN:
    """A missing or numeric -n: never injects, a line only when config is set."""

    @pytest.mark.parametrize(
        ("extra_args", "addopts"),
        [([], None), (["-n", "8"], None), ([], "-n 4"), (["-n", "0"], None)],
    )
    def test_config_not_set_gives_no_line(
        self, tmp_path: Path, extra_args: list[str], addopts: str | None
    ) -> None:
        env_vars = {"A": "1"}
        plan = resolve_workers(
            _effective(tmp_path, extra_args, addopts=addopts), env_vars
        )
        assert plan == WorkersPlan(env_vars, False, None)
        assert plan.env is env_vars

    def test_no_n_without_env_vars(self, tmp_path: Path) -> None:
        plan = resolve_workers(_effective(tmp_path), None)
        assert plan == WorkersPlan(None, False, None)

    @pytest.mark.parametrize(
        ("extra_args", "env_vars", "addopts", "note"),
        [
            (
                [],
                None,
                "-n 8",
                "workers: 8 (-n 8 from pyproject.toml addopts; "
                "pytest_workers applies to -n auto only)",
            ),
            (
                ["-n", "0"],
                None,
                None,
                "workers: serial (-n 0 from extra_args; "
                "pytest_workers applies to -n auto only)",
            ),
            (
                ["-o", "addopts=-n 3"],
                None,
                "-n auto",
                "workers: 3 (-n 3 from -o addopts; "
                "pytest_workers applies to -n auto only)",
            ),
            (
                [],
                {"PYTEST_ADDOPTS": "-n 2"},
                None,
                "workers: 2 (-n 2 from PYTEST_ADDOPTS; "
                "pytest_workers applies to -n auto only)",
            ),
            (
                [],
                None,
                None,
                "workers: no -n (pytest_workers applies to -n auto only)",
            ),
        ],
    )
    def test_config_set_explains_it_does_not_apply(
        self,
        tmp_path: Path,
        user_config: UserConfig,
        extra_args: list[str],
        env_vars: dict[str, str] | None,
        addopts: str | None,
        note: str,
    ) -> None:
        user_config(_config("4"))
        plan = resolve_workers(
            _effective(tmp_path, extra_args, env_vars, addopts), env_vars
        )
        assert plan == WorkersPlan(env_vars, False, note)
        assert plan.env is env_vars

    def test_invalid_config_counts_as_set(
        self, tmp_path: Path, user_config: UserConfig
    ) -> None:
        user_config("not = [toml")
        plan = resolve_workers(_effective(tmp_path), None)
        assert plan.note == (
            "workers: no -n (pytest_workers applies to -n auto only; "
            "ignored config.toml: invalid TOML)"
        )


class TestConfigValue:
    """-n auto with a non-auto config value, or off Windows."""

    @pytest.mark.parametrize(
        ("value", "note", "serial"),
        [
            ("4", "workers: 4 (config.toml)", False),
            ("0", "workers: serial (config.toml)", True),
            ("1", "workers: 1 (config.toml)", False),
        ],
    )
    def test_integer_is_injected(
        self,
        tmp_path: Path,
        user_config: UserConfig,
        value: str,
        note: str,
        serial: bool,
    ) -> None:
        user_config(_config(value))
        env_vars = {"A": "1"}
        before = dict(env_vars)
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), env_vars)
        assert plan == WorkersPlan({"A": "1", ENV_KEY: value}, serial, note)
        assert env_vars == before

    def test_integer_without_env_vars(
        self, tmp_path: Path, user_config: UserConfig
    ) -> None:
        user_config(_config("4"))
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), None)
        assert plan.env == {ENV_KEY: "4"}

    def test_all_leaves_xdist_default(
        self, tmp_path: Path, user_config: UserConfig
    ) -> None:
        user_config(_config('"all"'))
        env_vars = {"A": "1"}
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), env_vars)
        assert plan == WorkersPlan(
            env_vars, False, "workers: xdist default (all, config.toml)"
        )
        assert plan.env is env_vars

    @pytest.mark.parametrize("config", [None, '"auto"'])
    def test_auto_not_windows(
        self, tmp_path: Path, user_config: UserConfig, config: str | None
    ) -> None:
        if config is not None:
            user_config(_config(config))
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), None)
        assert plan == WorkersPlan(
            None, False, "workers: xdist default (auto, not Windows)"
        )

    def test_auto_from_pyproject_addopts(self, tmp_path: Path) -> None:
        plan = resolve_workers(_effective(tmp_path, addopts="-n auto"), None)
        assert plan.note == "workers: xdist default (auto, not Windows)"


class TestWindowsSizing:
    """-n auto / logical on Windows: sized from the sampled CPU load."""

    @pytest.mark.parametrize(
        ("idle", "count", "note"),
        [
            (Fraction(29, 100), 3, "workers: 3 (auto, Windows, CPU load 71 %)"),
            (Fraction(8, 100), 0, "workers: serial (auto, Windows, CPU load 92 %)"),
            (Fraction(1, 100), 0, "workers: serial (auto, Windows, CPU load 99 %)"),
            (Fraction(1), 12, "workers: 12 (auto, Windows, CPU load 0 %)"),
            (Fraction(23, 24), 11, "workers: 11 (auto, Windows, CPU load 4 %)"),
        ],
    )
    def test_sized_by_load(
        self,
        tmp_path: Path,
        windows: SetIdle,
        idle: Fraction,
        count: int,
        note: str,
    ) -> None:
        windows(idle)
        env_vars = {"A": "1"}
        before = dict(env_vars)
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), env_vars)
        assert plan == WorkersPlan({"A": "1", ENV_KEY: str(count)}, count == 0, note)
        assert env_vars == before

    @pytest.mark.parametrize("args", [["-n", "logical"], ["--numprocesses=logical"]])
    def test_logical_is_sized_like_auto(
        self, tmp_path: Path, windows: SetIdle, args: list[str]
    ) -> None:
        windows(Fraction(29, 100))
        plan = resolve_workers(_effective(tmp_path, args), None)
        assert plan == WorkersPlan(
            {ENV_KEY: "3"}, False, "workers: 3 (auto, Windows, CPU load 71 %)"
        )

    def test_sampler_unavailable(self, tmp_path: Path, windows: SetIdle) -> None:
        windows(None)
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), None)
        assert plan == WorkersPlan(
            None, False, "workers: xdist default (auto, Windows, CPU load unavailable)"
        )

    def test_cpu_count_unavailable(
        self, tmp_path: Path, windows: SetIdle, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(_CPU_COUNT, lambda: None)
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), None)
        assert plan == WorkersPlan(
            None, False, "workers: xdist default (auto, Windows, CPU load unavailable)"
        )

    def test_invalid_value_is_reported_after_the_reason(
        self, tmp_path: Path, windows: SetIdle, user_config: UserConfig
    ) -> None:
        user_config(_config('"x"'))
        windows(Fraction(52, 100))
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), None)
        assert plan == WorkersPlan(
            {ENV_KEY: "6"},
            False,
            "workers: 6 (auto, Windows, CPU load 48 %; "
            'ignored pytest_workers = "x" in config.toml)',
        )


class TestPreset:
    """A pre-set PYTEST_XDIST_AUTO_NUM_WORKERS wins and skips sampling."""

    @pytest.mark.parametrize(
        ("value", "note", "serial"),
        [
            ("6", "workers: 6 (PYTEST_XDIST_AUTO_NUM_WORKERS)", False),
            ("0", "workers: serial (PYTEST_XDIST_AUTO_NUM_WORKERS)", True),
            (
                "x",
                "workers: xdist default "
                '(PYTEST_XDIST_AUTO_NUM_WORKERS="x" is not an integer)',
                False,
            ),
        ],
    )
    def test_from_env_vars(
        self, tmp_path: Path, windows: SetIdle, value: str, note: str, serial: bool
    ) -> None:
        sampler = windows(Fraction(1, 2))
        env_vars = {ENV_KEY: value, "A": "1"}
        before = dict(env_vars)
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), env_vars)
        assert plan == WorkersPlan(env_vars, serial, note)
        assert plan.env is env_vars
        assert env_vars == before
        sampler.assert_not_called()

    def test_from_os_environ(
        self, tmp_path: Path, windows: SetIdle, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        sampler = windows(Fraction(1, 2))
        monkeypatch.setenv(ENV_KEY, "6")
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), None)
        assert plan == WorkersPlan(
            None, False, "workers: 6 (PYTEST_XDIST_AUTO_NUM_WORKERS)"
        )
        sampler.assert_not_called()

    def test_caller_value_is_reported_over_the_server(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ENV_KEY, "3")
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), {ENV_KEY: "6"})
        assert plan.note == "workers: 6 (PYTEST_XDIST_AUTO_NUM_WORKERS)"

    def test_still_reports_invalid_config(
        self, tmp_path: Path, windows: SetIdle, user_config: UserConfig
    ) -> None:
        user_config(_config('"x"'))
        sampler = windows(Fraction(1, 2))
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), {ENV_KEY: "6"})
        assert plan.note == (
            "workers: 6 (PYTEST_XDIST_AUTO_NUM_WORKERS; "
            'ignored pytest_workers = "x" in config.toml)'
        )
        sampler.assert_not_called()

    def test_preset_wins_over_config_integer(
        self, tmp_path: Path, user_config: UserConfig
    ) -> None:
        user_config(_config("4"))
        env_vars = {ENV_KEY: "2"}
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), env_vars)
        assert plan == WorkersPlan(
            env_vars, False, "workers: 2 (PYTEST_XDIST_AUTO_NUM_WORKERS)"
        )

    def test_empty_caller_value_counts_as_unset(
        self, tmp_path: Path, windows: SetIdle
    ) -> None:
        windows(Fraction(29, 100))
        env_vars = {ENV_KEY: "", "A": "1"}
        before = dict(env_vars)
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), env_vars)
        assert plan == WorkersPlan(
            {"A": "1", ENV_KEY: "3"}, False, "workers: 3 (auto, Windows, CPU load 71 %)"
        )
        assert env_vars == before

    def test_empty_os_environ_value_counts_as_unset(
        self, tmp_path: Path, user_config: UserConfig, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        user_config(_config("4"))
        monkeypatch.setenv(ENV_KEY, "")
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), None)
        assert plan == WorkersPlan({ENV_KEY: "4"}, False, "workers: 4 (config.toml)")

    @pytest.mark.skipif(os.name != "nt", reason="env keys are case-insensitive on nt")
    def test_lowercase_caller_key_is_dropped_on_windows(
        self, tmp_path: Path, user_config: UserConfig
    ) -> None:
        user_config(_config("4"))
        env_vars = {ENV_KEY.lower(): "", "A": "1"}
        before = dict(env_vars)
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), env_vars)
        assert plan.env == {"A": "1", ENV_KEY: "4"}
        assert env_vars == before

    @pytest.mark.skipif(os.name != "nt", reason="env keys are case-insensitive on nt")
    def test_lowercase_caller_key_is_a_preset_on_windows(self, tmp_path: Path) -> None:
        env_vars = {ENV_KEY.lower(): "5"}
        plan = resolve_workers(_effective(tmp_path, ["-n", "auto"]), env_vars)
        assert plan == WorkersPlan(
            env_vars, False, "workers: 5 (PYTEST_XDIST_AUTO_NUM_WORKERS)"
        )
