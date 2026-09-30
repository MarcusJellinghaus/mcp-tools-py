"""Tests for formatter.runner orchestration logic."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from mcp_tools_py.formatter import black_runner
from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.formatter.runner import run_format_code
from mcp_tools_py.utils.python_environment import PythonEnvironment
from tests.conftest import make_command_result
from tests.test_tool_availability._helpers import _dummy_python

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
            result = run_format_code(_PYTHON, _PROJECT, _DIRS, steps=["isort", "black"])

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
        with pytest.raises(ValueError, match=r"Invalid formatter steps: \['ruff'\]"):
            run_format_code(_PYTHON, _PROJECT, _DIRS, steps=["ruff"])

    def test_empty_steps_raises_valueerror(self) -> None:
        fake = MagicMock(return_value=_make_result())
        runners = {"isort": fake, "black": fake}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            with pytest.raises(ValueError, match="empty"):
                run_format_code(_PYTHON, _PROJECT, _DIRS, steps=[])

        fake.assert_not_called()


class TestResolution:
    """steps=None resolves from the project; an explicit list does not."""

    def test_none_calls_resolve_steps(self) -> None:
        fake = MagicMock(return_value=_make_result())
        resolve = MagicMock(return_value=["ruff_imports", "ruff_format"])
        runners = {"ruff_imports": fake, "ruff_format": fake}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            mp.setattr("mcp_tools_py.formatter.runner.resolve_steps", resolve)
            result = run_format_code(_PYTHON, _PROJECT, _DIRS)

        resolve.assert_called_once_with(_PROJECT)
        assert list(result) == ["ruff_imports", "ruff_format"]

    def test_explicit_steps_skip_resolve_steps(self) -> None:
        fake = MagicMock(return_value=_make_result())
        resolve = MagicMock()
        runners = {"isort": fake, "black": fake}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            mp.setattr("mcp_tools_py.formatter.runner.resolve_steps", resolve)
            run_format_code(_PYTHON, _PROJECT, _DIRS, steps=["isort", "black"])

        resolve.assert_not_called()


class TestIgnoredPythonExecutable:
    """The deprecated python_executable never selects the binary."""

    def test_bogus_python_executable_does_not_change_binary(
        self, tmp_path: Path
    ) -> None:
        environment = PythonEnvironment(Path(_dummy_python(tmp_path, "black")))
        expected = environment.binary("black")
        assert expected is not None

        mock_exec = MagicMock(return_value=make_command_result())
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(black_runner, "execute_command", mock_exec)
            mp.setattr(black_runner, "version_line", MagicMock(return_value="v"))
            run_format_code(
                "/no/such/python",
                tmp_path,
                _DIRS,
                steps=["black"],
                environment=environment,
            )

        assert mock_exec.call_args[0][0][0] == str(expected)


class TestFailFast:
    """Fail-fast behaviour in normal mode."""

    def test_stops_on_failure(self) -> None:
        fake_isort = MagicMock(return_value=_make_result(output="error", success=False))
        fake_black = MagicMock(return_value=_make_result())

        runners = {"isort": fake_isort, "black": fake_black}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            result = run_format_code(_PYTHON, _PROJECT, _DIRS, steps=["isort", "black"])

        fake_isort.assert_called_once()
        fake_black.assert_not_called()
        assert list(result.keys()) == ["isort"]

    def test_continues_past_step_with_unparsable_files(self) -> None:
        fake_imports = MagicMock(
            return_value=FormatterResult(
                output="syntax error",
                success=False,
                files_changed=[],
                unparsable_files=["src/bad.py"],
            )
        )
        fake_format = MagicMock(return_value=_make_result())

        runners = {"ruff_imports": fake_imports, "ruff_format": fake_format}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            result = run_format_code(
                _PYTHON, _PROJECT, _DIRS, steps=["ruff_imports", "ruff_format"]
            )

        fake_format.assert_called_once()
        assert list(result) == ["ruff_imports", "ruff_format"]
        assert result["ruff_imports"].success is False

    def test_stops_on_failure_without_unparsable_files(self) -> None:
        fake_imports = MagicMock(
            return_value=_make_result(output="config error", success=False)
        )
        fake_format = MagicMock(return_value=_make_result())

        runners = {"ruff_imports": fake_imports, "ruff_format": fake_format}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            result = run_format_code(
                _PYTHON, _PROJECT, _DIRS, steps=["ruff_imports", "ruff_format"]
            )

        fake_format.assert_not_called()
        assert list(result) == ["ruff_imports"]


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
            result = run_format_code(
                _PYTHON, _PROJECT, _DIRS, steps=["isort", "black"], check_only=True
            )

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
            run_format_code(
                _PYTHON, _PROJECT, _DIRS, steps=["isort", "black"], check_only=True
            )

        for call in fake.call_args_list:
            assert call[0][3] is True  # check_only positional arg


class TestTimeouts:
    """Per-step timeout budgets."""

    def test_each_step_receives_its_own_timeout(self) -> None:
        fake_isort = MagicMock(return_value=_make_result())
        fake_black = MagicMock(return_value=_make_result())

        runners = {"isort": fake_isort, "black": fake_black}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            run_format_code(
                _PYTHON,
                _PROJECT,
                _DIRS,
                steps=["isort", "black"],
                timeouts={"isort": 30, "black": 90},
            )

        assert fake_isort.call_args[0][4] == 30
        assert fake_black.call_args[0][4] == 90

    def test_missing_timeouts_use_default(self) -> None:
        fake_isort = MagicMock(return_value=_make_result())
        fake_black = MagicMock(return_value=_make_result())

        runners = {"isort": fake_isort, "black": fake_black}
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("mcp_tools_py.formatter.runner._STEP_RUNNERS", runners)
            run_format_code(_PYTHON, _PROJECT, _DIRS, steps=["isort", "black"])

        assert fake_isort.call_args[0][4] == 120
        assert fake_black.call_args[0][4] == 120
