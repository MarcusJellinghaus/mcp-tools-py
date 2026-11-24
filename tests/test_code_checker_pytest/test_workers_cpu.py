"""Tests for the CPU sampler in workers.py: math, median and the raw wrapper."""

import sys
from collections.abc import Iterator
from fractions import Fraction

import pytest

from mcp_tools_py.code_checker_pytest import workers
from mcp_tools_py.code_checker_pytest.workers import (
    SystemTimes,
    idle_fraction,
    sample_idle,
    workers_for,
)
from mcp_tools_py.code_checker_pytest.workers import (
    _get_system_times as real_get_system_times,
)
from mcp_tools_py.code_checker_pytest.workers import _is_windows as real_is_windows


def _readings(deltas: list[tuple[int, int, int]]) -> list[SystemTimes]:
    """Cumulative readings from (d_idle, d_kernel, d_user) deltas, starting at 1000."""
    idle, kernel, user = 1000, 5000, 3000
    readings: list[SystemTimes] = [(idle, kernel, user)]
    for d_idle, d_kernel, d_user in deltas:
        idle, kernel, user = idle + d_idle, kernel + d_kernel, user + d_user
        readings.append((idle, kernel, user))
    return readings


def _patch_readings(
    monkeypatch: pytest.MonkeyPatch, readings: list[SystemTimes | None]
) -> None:
    """Make workers._get_system_times return *readings* in order."""
    iterator: Iterator[SystemTimes | None] = iter(readings)
    monkeypatch.setattr(workers, "_get_system_times", lambda: next(iterator))


@pytest.mark.parametrize(
    ("logical", "idle", "expected"),
    [
        (24, Fraction(1), 12),
        (24, Fraction(3, 4), 9),
        (24, Fraction(1, 2), 6),
        (24, Fraction(1, 4), 3),
        (24, Fraction(1, 6), 2),
        (24, Fraction(4, 25), 0),
        (24, Fraction(0), 0),
        (24, Fraction(23, 24), 11),
    ],
)
def test_workers_for(logical: int, idle: Fraction, expected: int) -> None:
    assert workers_for(logical, idle) == expected


def test_idle_fraction_normal_delta() -> None:
    before: SystemTimes = (100, 400, 200)
    after: SystemTimes = (130, 460, 240)
    assert idle_fraction(before, after) == Fraction(30, 100)


def test_idle_fraction_zero_total_delta_is_none() -> None:
    reading: SystemTimes = (100, 400, 200)
    assert idle_fraction(reading, reading) is None


def test_sample_idle_median_ignores_burst(monkeypatch: pytest.MonkeyPatch) -> None:
    # Idle fractions per delta: 6/10, 7/10, 0 (burst), 8/10, 9/10 -> median 7/10.
    deltas = [(6, 8, 2), (7, 8, 2), (0, 5, 5), (8, 9, 1), (9, 9, 1)]
    _patch_readings(monkeypatch, list(_readings(deltas)))
    assert sample_idle(interval=0) == Fraction(7, 10)


def test_sample_idle_none_reading_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    readings: list[SystemTimes | None] = list(_readings([(5, 8, 2)] * 5))
    readings[3] = None
    _patch_readings(monkeypatch, readings)
    assert sample_idle(interval=0) is None


def test_sample_idle_zero_delta_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    deltas = [(5, 8, 2), (5, 8, 2), (0, 0, 0), (5, 8, 2), (5, 8, 2)]
    _patch_readings(monkeypatch, list(_readings(deltas)))
    assert sample_idle(interval=0) is None


def test_autouse_default_does_not_sample() -> None:
    assert workers._is_windows() is False
    assert sample_idle(interval=0) is None


def test_real_is_windows_matches_platform() -> None:
    assert real_is_windows() is (sys.platform == "win32")


@pytest.mark.skipif(sys.platform != "win32", reason="GetSystemTimes is Windows only")
def test_real_get_system_times_on_windows() -> None:
    times = real_get_system_times()
    assert times is not None
    idle, kernel, user = times
    assert all(isinstance(value, int) and value >= 0 for value in times)
    assert kernel >= idle
    assert user >= 0
