"""Integration tests: -n auto sized through PYTEST_XDIST_AUTO_NUM_WORKERS."""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from mcp_tools_py.code_checker_pytest.runners import check_code_with_pytest
from mcp_tools_py.code_checker_pytest.verdict import RunStatus

UserConfig = Callable[[str], Path]
_SERIAL_TEST = (
    "import os\n"
    "\n"
    "\n"
    "def test_serial():\n"
    '    assert "PYTEST_XDIST_WORKER" not in os.environ\n'
)
_PARALLEL_TEST = (
    "import os\n"
    "\n"
    "\n"
    "def test_parallel():\n"
    '    assert "PYTEST_XDIST_WORKER" in os.environ\n'
)


def _project(tmp_path: Path, test_source: str) -> Path:
    """A project under tmp_path with one test file in tests/."""
    project = tmp_path / "project"
    tests_dir = project / "tests"
    tests_dir.mkdir(parents=True)
    (tests_dir / "test_workers.py").write_text(test_source, encoding="utf-8")
    return project


def _run(project: Path, env_vars: dict[str, str] | None = None) -> dict[str, Any]:
    return check_code_with_pytest(
        str(project),
        python_executable=sys.executable,
        extra_args=["-n", "auto"],
        env_vars=env_vars,
        timeout_seconds=120,
    )


@pytest.mark.integration
def test_env_zero_runs_serially(tmp_path: Path) -> None:
    """PYTEST_XDIST_AUTO_NUM_WORKERS=0 makes xdist run without workers."""
    pytest.importorskip("xdist")
    project = _project(tmp_path, _SERIAL_TEST)

    result = _run(project, {"PYTEST_XDIST_AUTO_NUM_WORKERS": "0"})

    assert result["verdict"].status is RunStatus.PASSED
    assert result["workers_serial"] is True
    assert result["workers_note"] == "workers: serial (PYTEST_XDIST_AUTO_NUM_WORKERS)"


@pytest.mark.integration
def test_config_zero_runs_serially(tmp_path: Path, user_config: UserConfig) -> None:
    """pytest_workers = 0 makes -n auto run without workers."""
    pytest.importorskip("xdist")
    project = _project(tmp_path, _SERIAL_TEST)
    user_config("[mcp_tools_py]\npytest_workers = 0\n")

    result = _run(project)

    assert result["verdict"].status is RunStatus.PASSED
    assert result["workers_serial"] is True
    assert result["workers_note"] == "workers: serial (config.toml)"


@pytest.mark.integration
def test_config_two_runs_in_workers(tmp_path: Path, user_config: UserConfig) -> None:
    """Control: pytest_workers = 2 runs the test inside an xdist worker."""
    pytest.importorskip("xdist")
    project = _project(tmp_path, _PARALLEL_TEST)
    user_config("[mcp_tools_py]\npytest_workers = 2\n")

    result = _run(project)

    assert result["verdict"].status is RunStatus.PASSED
    assert result["workers_serial"] is False
    assert result["workers_note"] == "workers: 2 (config.toml)"
