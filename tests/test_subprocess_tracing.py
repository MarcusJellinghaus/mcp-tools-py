"""Integration tests for tracing subprocesses, as this repo's coverage config does."""

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from tests._coverage_project import _PYPROJECT, _run_pytest_check

pytest.importorskip("pytest_cov")
pytest.importorskip("coverage", minversion="7.10")

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ROPE_CLI = _REPO_ROOT / "src" / "mcp_tools_py" / "refactoring" / "rope_cli.py"
_PROBE = _REPO_ROOT / "src" / "mcp_tools_py" / "utils" / "target_scripts" / "probe.py"

_TRACING_CONFIG = """
[tool.coverage.run]
patch = ["subprocess"]
"""

_COVERED = """\
def covered(x):
    return x + 1
"""

_SPAWNING_TEST = """\
import os
import subprocess
import sys
from pathlib import Path

from pkg.covered import covered

SRC = Path(__file__).resolve().parents[1] / "src"


def test_spawns_both_scripts():
    assert covered(1) == 2
    subprocess.run(
        [sys.executable, "-m", "pkg.rope_cli"],
        env={**os.environ, "PYTHONPATH": str(SRC)},
        check=False,
        capture_output=True,
    )
    subprocess.run(
        [sys.executable, str(SRC / "pkg" / "probe.py"), "info"],
        check=False,
        capture_output=True,
    )
"""


@pytest.fixture(autouse=True)
def _no_outer_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep an outer traced run from leaking into the nested one."""
    monkeypatch.delenv("COVERAGE_PROCESS_CONFIG", raising=False)


def _write_spawning_project(project_dir: Path, traced: bool) -> None:
    """Write a project whose test spawns copies of the two real scripts.

    The test also imports pkg.covered, so src/pkg/ doesn't collapse into one row
    of the zero-coverage list and each file keeps its own.
    """
    package = project_dir / "src" / "pkg"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "covered.py").write_text(_COVERED)
    shutil.copy(_ROPE_CLI, package / "rope_cli.py")
    shutil.copy(_PROBE, package / "probe.py")
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_spawn.py").write_text(_SPAWNING_TEST)
    (project_dir / "pyproject.toml").write_text(
        _PYPROJECT + (_TRACING_CONFIG if traced else "")
    )


def _zero_coverage_section(reply: str) -> str:
    """Return the digest's zero-coverage list, empty when it has none."""
    _, _, section = reply.partition("have no covered statements in this selection:")
    return section.split("\n\n")[0]


def test_this_repo_traces_subprocesses() -> None:
    """The setting the projects below are built around is the one this repo has."""
    with (_REPO_ROOT / "pyproject.toml").open("rb") as file:
        config = tomllib.load(file)

    assert "subprocess" in config["tool"]["coverage"]["run"]["patch"]


def test_traced_scripts_are_not_zero_coverage(tmp_path: Path) -> None:
    """With the setting, code that only ran in a subprocess counts as covered."""
    _write_spawning_project(tmp_path, traced=True)

    reply = _run_pytest_check(tmp_path)(coverage=True)

    assert "modules measured" in reply
    assert "⚠" not in reply
    section = _zero_coverage_section(reply)
    assert "rope_cli.py" not in section
    assert "probe.py" not in section


def test_untraced_scripts_are_zero_coverage(tmp_path: Path) -> None:
    """Without the setting both scripts are listed, so the test above can fail."""
    _write_spawning_project(tmp_path, traced=False)

    reply = _run_pytest_check(tmp_path)(coverage=True)

    section = _zero_coverage_section(reply)
    assert "rope_cli.py" in section
    assert "probe.py" in section


def test_traced_run_skips_the_startup_budget(tmp_path: Path) -> None:
    """This repo's own config makes the startup test skip under --cov."""
    env = {**os.environ, "COVERAGE_FILE": str(tmp_path / ".coverage")}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_startup_time.py::test_server_startup_within_budget",
            "-m",
            "integration",
            "--cov=src/mcp_tools_py/utils/target_scripts",
            "--cov-report=",
            "-n",
            "0",
            "-p",
            "no:cacheprovider",
        ],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 skipped" in result.stdout
