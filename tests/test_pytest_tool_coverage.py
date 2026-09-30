"""Integration test for run_pytest_check(coverage=True) against a real project."""

import importlib.util
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        importlib.util.find_spec("pytest_cov") is None,
        reason="pytest-cov is not installed",
    ),
]

_MODULE = """\
def covered(x):
    return x + 1


def uncovered(x):
    y = x * 2
    return y
"""

_TEST = """\
from pkg.mod import covered


def test_covered():
    assert covered(1) == 2
"""

_PYPROJECT = """\
[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
"""


def _run_pytest_check(project_dir: Path) -> Any:
    """Register the tools for project_dir under this interpreter.

    Returns:
        The registered run_pytest_check function.
    """
    with patch("mcp.server.fastmcp.FastMCP") as mock_fastmcp:
        mock_tool = MagicMock()
        mock_fastmcp.return_value.tool.return_value = mock_tool

        from mcp_tools_py.server import ToolServer

        with patch.object(
            ToolServer, "_warn_missing_console_scripts", return_value=None
        ):
            ToolServer(project_dir=project_dir, python_executable=sys.executable)

    tools = {f.__name__: f for call in mock_tool.call_args_list for f in [call[0][0]]}
    return tools["run_pytest_check"]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A project with one tested and one untested function, fail_under = 99."""
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("")
    (tmp_path / "src" / "pkg" / "mod.py").write_text(_MODULE)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_mod.py").write_text(_TEST)
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT)
    (tmp_path / ".coveragerc").write_text("[report]\nfail_under = 99\n")
    return tmp_path


def test_coverage_digest_from_a_real_run(project: Path) -> None:
    """The digest is appended, fail_under is reported but not applied."""
    result = _run_pytest_check(project)(coverage=True)

    assert "Passed: 1" in result or "passed successfully" in result
    assert "stmts" in result
    assert "selection: full suite" in result
    assert "fail_under=99 is configured; not applied to this run" in result
    assert "uncovered  6-7" in result
    assert "Warning: tests failed" not in result


def test_coverage_leaves_the_project_clean(project: Path) -> None:
    """No coverage data or report lands in the project directory."""
    _run_pytest_check(project)(coverage=True)

    leftovers = [p.name for p in project.iterdir() if "coverage" in p.name]
    assert leftovers == [".coveragerc"]
