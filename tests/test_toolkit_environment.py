"""Tests for PythonToolkit's project environment from VIRTUAL_ENV."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from mcp_coder_utils.toolkit import ActionRequest

from mcp_tools_py.toolkit import PythonToolkit, _build_context
from mcp_tools_py.utils import python_environment


def _fake_venv(root: Path) -> Path:
    """Create an empty interpreter file where PythonEnvironment.resolve looks.

    Returns:
        The interpreter path.
    """
    if python_environment._IS_WINDOWS:  # pylint: disable=protected-access
        interpreter = root / "Scripts" / "python.exe"
    else:
        interpreter = root / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    return interpreter


class TestBuildContext:
    """_build_context resolves VIRTUAL_ENV when set, else sys.executable."""

    def test_unset_uses_sys_executable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("VIRTUAL_ENV", raising=False)

        context = _build_context(tmp_path)

        assert context.environment.interpreter == Path(sys.executable)

    def test_empty_is_treated_as_unset(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIRTUAL_ENV", "")

        context = _build_context(tmp_path)

        assert context.environment.interpreter == Path(sys.executable)

    def test_set_uses_its_interpreter(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        venv = tmp_path / "venv"
        interpreter = _fake_venv(venv)
        monkeypatch.setenv("VIRTUAL_ENV", str(venv))

        context = _build_context(tmp_path)

        assert context.environment.interpreter == interpreter
        assert context.tool_environment.interpreter == Path(sys.executable)


class TestRunStaleVirtualEnv:
    """A VIRTUAL_ENV without an interpreter is an error, never a fallback."""

    def test_stale_run_is_error_naming_virtual_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "missing"))

        with patch("mcp_tools_py.toolkit.check_code_with_pytest") as pytest_run:
            result = PythonToolkit().run(
                ActionRequest(
                    action="test", depth="standard", project_dir=tmp_path, params={}
                )
            )

        assert result.status == "error"
        assert "VIRTUAL_ENV" in result.summary
        pytest_run.assert_not_called()
