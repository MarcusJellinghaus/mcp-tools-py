"""The Python environment that tools run in and that Python names resolve in."""

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Whether the interpreter layout is the Windows one: `Scripts/python.exe` and
# `<name>.exe` console scripts, rather than `bin/python` and bare `<name>`.
# Read from here rather than from `os.name` directly so that a test can select
# the other layout: patching `os.name` would also change which `pathlib` flavour
# `Path(...)` instantiates, which fails on the platform not being simulated.
_IS_WINDOWS = os.name == "nt"


@dataclass(frozen=True)
class PythonEnvironment:
    """The Python environment that tools run in and that Python names resolve in.

    Attributes:
        interpreter: Path to the Python interpreter of the environment.
    """

    interpreter: Path

    @classmethod
    def resolve(
        cls,
        python_executable: Optional[str] = None,
        venv_path: Optional[str] = None,
    ) -> "PythonEnvironment":
        """Centralize venv -> python_executable -> sys.executable resolution.

        A name without a directory part is looked up on PATH, so
        `--python-executable python3` resolves to the interpreter a subprocess
        would have started.

        Args:
            python_executable: Path to a Python interpreter, or a bare name to
                look up on PATH.
            venv_path: Deprecated path to a virtual environment. When given, it
                wins over `python_executable`.

        Returns:
            The resolved environment.

        Raises:
            FileNotFoundError: If the resolved interpreter neither exists nor
                is found on PATH.
        """
        if venv_path:
            if _IS_WINDOWS:
                python = Path(venv_path) / "Scripts" / "python.exe"
            else:
                python = Path(venv_path) / "bin" / "python"
            source = "--venv-path"
        elif python_executable:
            python, source = Path(python_executable), "--python-executable"
        else:
            python, source = Path(sys.executable), "sys.executable"

        if not os.path.exists(python):
            on_path = shutil.which(str(python))
            if on_path is None:
                raise FileNotFoundError(
                    f"Python interpreter not found: {python} (from {source})"
                )
            return cls(Path(on_path))
        return cls(python)

    @property
    def bin_dir(self) -> Path:
        """Directory holding the interpreter and its console scripts.

        Returns:
            The interpreter's parent directory.
        """
        return self.interpreter.parent

    def binary(self, name: str) -> Optional[Path]:
        """Locate a console script next to the interpreter.

        Args:
            name: Console-script filename, without any platform suffix.

        Returns:
            Path to the console script, or None when it is not there.
        """
        path = self.bin_dir / (f"{name}.exe" if _IS_WINDOWS else name)
        return path if os.path.exists(path) else None
