"""A real project to run coverage against, and the tool that runs it."""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

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


def _write_project(project_dir: Path) -> None:
    """Write a project with one tested and one untested function, fail_under = 99."""
    (project_dir / "src" / "pkg").mkdir(parents=True)
    (project_dir / "src" / "pkg" / "__init__.py").write_text("")
    (project_dir / "src" / "pkg" / "mod.py").write_text(_MODULE)
    (project_dir / "tests").mkdir()
    (project_dir / "tests" / "test_mod.py").write_text(_TEST)
    (project_dir / "pyproject.toml").write_text(_PYPROJECT)
    (project_dir / ".coveragerc").write_text("[report]\nfail_under = 99\n")
