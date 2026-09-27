"""The lint-imports PYTHONPATH bridge, running for real.

Nothing here is patched.  The config read, the `locate` probe and the
`PYTHONPATH` handover all run, with the real lint-imports from the tool env and
a real project interpreter built by `python -m venv`.  Everything else in the
suite mocks the bridge, so this file is the only evidence it works — and the
only thing that would catch lint-imports reading an installed copy of the
project instead of the working tree.
"""

import os
import sys
from pathlib import Path
from typing import Optional

import pytest

from mcp_tools_py.code_checker_lint_imports import run_lint_imports_check_impl
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.subprocess_runner import execute_command

# Unique enough that no environment anywhere has it installed: a BROKEN verdict
# can only come from the bridge having handed over the source tree below.
_PACKAGE = "bridgepkg_i233"
_CONTRACT = "a must not import b"

_VENV_TIMEOUT = 120


def _lint_imports() -> Optional[Path]:
    """Locate the lint-imports console script in the tool env.

    Returns:
        Path to the script, or None when it is not installed.
    """
    return PythonEnvironment.resolve().binary("lint-imports")


def _config(root_package: str) -> str:
    """Build an import-linter config whose one contract `a -> b` breaks.

    Args:
        root_package: Name to check, whether or not it can be found.

    Returns:
        The `.importlinter` contents.
    """
    return (
        "[importlinter]\n"
        f"root_package = {root_package}\n"
        "\n"
        "[importlinter:contract:no-a-to-b]\n"
        f"name = {_CONTRACT}\n"
        "type = forbidden\n"
        "source_modules =\n"
        f"    {root_package}.a\n"
        "forbidden_modules =\n"
        f"    {root_package}.b\n"
    )


def _build_project(tmp_path: Path) -> Path:
    """Write a src-layout project whose package exists only under `src/`.

    lint-imports puts its own working directory on `sys.path`, so keeping the
    package out of the project root is what forces the bridge to be the thing
    that finds it.

    Args:
        tmp_path: Directory to build in.

    Returns:
        The project directory.
    """
    project = tmp_path / "proj"
    package = project / "src" / _PACKAGE
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "a.py").write_text(
        f"from {_PACKAGE} import b\n\nvalue = b.value\n", encoding="utf-8"
    )
    (package / "b.py").write_text("value = 1\n", encoding="utf-8")
    (project / ".importlinter").write_text(_config(_PACKAGE), encoding="utf-8")
    return project


def _project_interpreter(tmp_path: Path, source_dir: Path) -> Path:
    """Build a venv that can import from `source_dir`, without pip or network.

    A `.pth` file naming the source tree is the whole install: the interpreter
    then answers the `locate` probe with `source_dir`, which is not one of its
    own site directories and so is usable.

    Args:
        tmp_path: Directory to build the venv in.
        source_dir: Source tree the venv should be able to import from.

    Returns:
        Path to the venv's interpreter.
    """
    venv = tmp_path / "venv"
    created = execute_command(
        [sys.executable, "-m", "venv", "--without-pip", str(venv)],
        timeout_seconds=_VENV_TIMEOUT,
    )
    assert created.return_code == 0, created.stdout + created.stderr

    suffix = ".exe" if os.name == "nt" else ""
    interpreter = venv / ("Scripts" if os.name == "nt" else "bin") / f"python{suffix}"
    assert interpreter.is_file(), f"no interpreter at {interpreter}"

    asked = execute_command(
        [str(interpreter), "-c", "import site; print(site.getsitepackages()[-1])"],
        timeout_seconds=_VENV_TIMEOUT,
    )
    assert asked.return_code == 0, asked.stdout + asked.stderr
    site_packages = Path(asked.stdout.strip())
    site_packages.mkdir(parents=True, exist_ok=True)
    (site_packages / "bridge_i233.pth").write_text(f"{source_dir}\n", encoding="utf-8")
    return interpreter


@pytest.mark.integration
def test_root_package_is_found_through_the_bridge(tmp_path: Path) -> None:
    """The contract breaks, so the bridge handed over the real source tree."""
    binary = _lint_imports()
    if binary is None:
        pytest.skip("lint-imports is not installed next to this interpreter")

    project = _build_project(tmp_path)
    interpreter = _project_interpreter(tmp_path, project / "src")

    report = run_lint_imports_check_impl(
        str(binary),
        str(project),
        extra_args=["--no-cache"],
        python_executable=str(interpreter),
    )

    assert "BROKEN" in report, report
    assert _CONTRACT in report, report


@pytest.mark.integration
def test_unfindable_root_package_never_reports_passed(tmp_path: Path) -> None:
    """A package no interpreter has must surface an error, never a green run."""
    binary = _lint_imports()
    if binary is None:
        pytest.skip("lint-imports is not installed next to this interpreter")

    project = _build_project(tmp_path)
    interpreter = _project_interpreter(tmp_path, project / "src")
    (project / ".importlinter").write_text(_config("nosuchpkg_i233"), encoding="utf-8")

    report = run_lint_imports_check_impl(
        str(binary),
        str(project),
        extra_args=["--no-cache"],
        python_executable=str(interpreter),
    )

    assert "=== PASSED ===" not in report, report
