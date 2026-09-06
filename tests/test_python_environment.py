"""Tests for the PythonEnvironment value object."""

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from mcp_tools_py.utils.python_environment import PythonEnvironment


def _make_venv(tmp_path: Path, is_windows: bool) -> Path:
    """Create a venv layout for the given platform and return its interpreter."""
    sub = "Scripts" if is_windows else "bin"
    exe = "python.exe" if is_windows else "python"
    bin_dir = tmp_path / sub
    bin_dir.mkdir(exist_ok=True)
    interpreter = bin_dir / exe
    interpreter.write_text("")
    return interpreter


class TestResolve:
    """Test PythonEnvironment.resolve."""

    @pytest.mark.parametrize("is_windows", [True, False])
    def test_venv_path_wins_over_python_executable(
        self, tmp_path: Path, is_windows: bool
    ) -> None:
        """venv_path takes precedence and picks the platform's venv layout."""
        interpreter = _make_venv(tmp_path, is_windows)

        with patch("mcp_tools_py.utils.python_environment._IS_WINDOWS", is_windows):
            env = PythonEnvironment.resolve(
                python_executable=str(tmp_path / "ignored" / "python"),
                venv_path=str(tmp_path),
            )

        assert env.interpreter == interpreter

    def test_venv_path_missing_python_raises(self, tmp_path: Path) -> None:
        """A venv without an interpreter fails, naming --venv-path."""
        with pytest.raises(FileNotFoundError, match="--venv-path"):
            PythonEnvironment.resolve(venv_path=str(tmp_path / "empty"))

    def test_python_executable_used_verbatim(self, tmp_path: Path) -> None:
        """An existing python_executable is used as given."""
        interpreter = tmp_path / "python"
        interpreter.write_text("")

        env = PythonEnvironment.resolve(python_executable=str(interpreter))

        assert env.interpreter == interpreter

    def test_python_executable_missing_raises(self, tmp_path: Path) -> None:
        """A path that neither exists nor is on PATH fails, naming the flag."""
        missing = tmp_path / "missing" / "python3.11"

        with pytest.raises(FileNotFoundError, match="--python-executable"):
            PythonEnvironment.resolve(python_executable=str(missing))

    def test_bare_name_resolved_on_path(self) -> None:
        """A name without a directory part is looked up on PATH."""
        with patch(
            "mcp_tools_py.utils.python_environment.shutil.which",
            return_value="/usr/bin/python3",
        ) as mock_which:
            env = PythonEnvironment.resolve(python_executable="python3")

        assert env.interpreter == Path("/usr/bin/python3")
        mock_which.assert_called_once_with("python3")

    def test_sys_executable_fallback(self) -> None:
        """With neither argument set, the current interpreter is used."""
        env = PythonEnvironment.resolve()

        assert env.interpreter == Path(sys.executable)


class TestBinDir:
    """Test PythonEnvironment.bin_dir."""

    def test_bin_dir_is_interpreter_parent(self) -> None:
        """bin_dir is the directory holding the interpreter."""
        env = PythonEnvironment(interpreter=Path("/some/env/bin/python"))

        assert env.bin_dir == Path("/some/env/bin")


class TestBinary:
    """Test PythonEnvironment.binary."""

    def test_binary_found(self, tmp_path: Path) -> None:
        """An existing console script next to the interpreter is returned."""
        suffix = ".exe" if os.name == "nt" else ""
        script = tmp_path / f"ruff{suffix}"
        script.write_text("")
        env = PythonEnvironment(interpreter=tmp_path / "python")

        assert env.binary("ruff") == script

    def test_binary_missing_returns_none(self, tmp_path: Path) -> None:
        """A console script that is not on disk resolves to None."""
        env = PythonEnvironment(interpreter=tmp_path / "python")

        assert env.binary("ruff") is None

    def test_binary_found_with_only_python_executable(self, tmp_path: Path) -> None:
        """Console scripts are found next to a plain --python-executable."""
        interpreter = _make_venv(tmp_path, os.name == "nt")
        suffix = ".exe" if os.name == "nt" else ""
        (interpreter.parent / f"ruff{suffix}").write_text("")

        env = PythonEnvironment.resolve(python_executable=str(interpreter))

        assert env.binary("ruff") == interpreter.parent / f"ruff{suffix}"
