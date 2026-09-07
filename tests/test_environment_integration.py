"""End-to-end: both fixed tools resolve against a real, foreign venv.

Builds a throwaway virtual environment holding a package that the tool
environment does not have, then points the tools at it through
``--python-executable``.  This is the only place in the suite that would have
caught the reported bug: before the fix, ``get_library_source`` imported into
the server process and jedi fell back to ``VIRTUAL_ENV``.
"""

import os
import sys
import sysconfig
import venv
from pathlib import Path
from typing import Iterator

import pytest

from mcp_tools_py.inspect_library import _get_library_source
from mcp_tools_py.refactoring.jedi_tools import _get_project, list_symbols
from mcp_tools_py.utils.python_environment import PythonEnvironment

_PACKAGE_SOURCE = '''\
"""A package that exists only in the target venv."""


class Marker:
    """Proves the name was resolved in the target environment."""

    label = "probe-only"


def marker_function() -> str:
    """Return the marker label."""
    return Marker.label
'''


@pytest.fixture(autouse=True)
def _clear_project_cache() -> Iterator[None]:
    """Drop cached jedi projects so their child processes are released."""
    _get_project.cache_clear()
    yield
    _get_project.cache_clear()


@pytest.fixture
def foreign_environment(tmp_path: Path) -> PythonEnvironment:
    """Build a venv containing `probe_only_pkg`, absent from the tool env.

    Args:
        tmp_path: pytest's per-test temporary directory.

    Returns:
        The environment resolved from that venv's interpreter.
    """
    env_dir = tmp_path / "env"
    # pip is not needed: environment_path and probe.py only need an interpreter.
    venv.EnvBuilder(with_pip=False).create(env_dir)

    # The site-packages layout differs by platform, so ask sysconfig for it.
    paths = sysconfig.get_paths(
        vars={
            "base": str(env_dir),
            "platbase": str(env_dir),
            "installed_base": str(env_dir),
        }
    )
    package = Path(paths["purelib"]) / "probe_only_pkg"
    package.mkdir(parents=True, exist_ok=True)
    (package / "__init__.py").write_text(_PACKAGE_SOURCE, encoding="utf-8")

    python = Path(paths["scripts"]) / ("python.exe" if os.name == "nt" else "python")
    return PythonEnvironment.resolve(python_executable=str(python))


@pytest.mark.integration
def test_get_library_source_resolves_in_the_target_venv(
    foreign_environment: PythonEnvironment,
) -> None:
    """The package is found through the target venv and not through the tool env."""
    interpreter = str(foreign_environment.interpreter)

    found = _get_library_source("probe_only_pkg.Marker", 200, interpreter)
    assert "class Marker" in found

    missing = _get_library_source("probe_only_pkg.Marker", 200, sys.executable)
    assert "not found" in missing


@pytest.mark.integration
def test_list_symbols_runs_against_the_target_venv(
    tmp_path: Path, foreign_environment: PythonEnvironment
) -> None:
    """jedi builds its environment from the foreign venv and analyses the project.

    This is a smoke test, not an environment-sensitivity test: `list_symbols`
    and `find_references` only name symbols *within the project*, so no exposed
    jedi call resolves a third-party name the way `get_library_source` does.
    What it proves is that `InvalidPythonEnvironment` does not fire for a real
    foreign venv and that jedi's child process starts under it.  The
    environment-sensitive guarantee is the `environment_path` construction
    assertion in `tests/test_refactoring/test_jedi_tools.py`.
    """
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "sample.py").write_text(
        "def greet() -> str:\n"
        '    return "hi"\n'
        "\n"
        "\n"
        "class Widget:\n"
        "    pass\n",
        encoding="utf-8",
    )

    result = list_symbols(
        project_dir, "sample.py", str(foreign_environment.interpreter)
    )

    assert "greet" in result
    assert "Widget" in result
    assert "cannot analyse" not in result
