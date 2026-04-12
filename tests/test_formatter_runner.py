"""Tests for formatter.runner orchestration logic."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.formatter.runner import run_format_code

_PROJECT = Path("/fake/project")
_PYTHON = "/usr/bin/python3"
_DIRS = ["src"]


def _make_result(output: str = "ok", success: bool = True) -> FormatterResult:
    return FormatterResult(output=output, success=success, files_changed=[])


class TestDefaultSteps:
    """Default step ordering."""

    def test_runs_isort_then_black(self) -> None:
        call_order: list[str] = []

        def fake_isort(*_a: Any, **_k: Any) -> FormatterResult:
            call_order.append("isort")
            return _make_result()

        def fake_black(*_a: Any, **_k: Any) -> FormatterResult:
            call_order.append("black")
            return _make_result()

        runners = {"isort": fake_isort, "black": fake_black}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            result = run_format_code(_PYTHON, _PROJECT, _DIRS)

        assert call_order == ["isort", "black"]
        assert list(result.keys()) == ["isort", "black"]


class TestCustomSteps:
    """Custom step selection."""

    def test_runs_only_requested(self) -> None:
        fake_black = MagicMock(return_value=_make_result())
        fake_isort = MagicMock(return_value=_make_result())

        runners = {"isort": fake_isort, "black": fake_black}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            result = run_format_code(_PYTHON, _PROJECT, _DIRS, steps=["black"])

        fake_black.assert_called_once()
        fake_isort.assert_not_called()
        assert list(result.keys()) == ["black"]


class TestValidation:
    """Step name validation."""

    def test_invalid_step_raises_valueerror(self) -> None:
        with pytest.raises(ValueError, match="ruff"):
            run_format_code(_PYTHON, _PROJECT, _DIRS, steps=["ruff"])


class TestFailFast:
    """Fail-fast behaviour in normal mode."""

    def test_stops_on_failure(self) -> None:
        fake_isort = MagicMock(return_value=_make_result(output="error", success=False))
        fake_black = MagicMock(return_value=_make_result())

        runners = {"isort": fake_isort, "black": fake_black}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            result = run_format_code(_PYTHON, _PROJECT, _DIRS)

        fake_isort.assert_called_once()
        fake_black.assert_not_called()
        assert list(result.keys()) == ["isort"]


class TestCheckOnly:
    """check_only continues on failure."""

    def test_continues_on_failure(self) -> None:
        fake_isort = MagicMock(
            return_value=_make_result(output="needs fmt", success=False)
        )
        fake_black = MagicMock(
            return_value=_make_result(output="needs fmt", success=False)
        )

        runners = {"isort": fake_isort, "black": fake_black}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            result = run_format_code(_PYTHON, _PROJECT, _DIRS, check_only=True)

        fake_isort.assert_called_once()
        fake_black.assert_called_once()
        assert list(result.keys()) == ["isort", "black"]


class TestReturnValue:
    """Return dict keyed by step."""

    def test_keys_match_requested_steps(self) -> None:
        fake = MagicMock(return_value=_make_result())
        runners = {"isort": fake, "black": fake}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            result = run_format_code(_PYTHON, _PROJECT, _DIRS, steps=["black", "isort"])

        assert list(result.keys()) == ["black", "isort"]


class TestCheckOnlyForwarded:
    """check_only is forwarded to runners."""

    def test_passes_check_only_to_runners(self) -> None:
        fake = MagicMock(return_value=_make_result())
        runners = {"isort": fake, "black": fake}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            run_format_code(_PYTHON, _PROJECT, _DIRS, check_only=True)

        for call in fake.call_args_list:
            assert call[0][3] is True  # check_only positional arg
