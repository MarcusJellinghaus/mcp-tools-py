"""Tests for the run_deptry_check MCP tool."""

import textwrap
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.checker_tools import CheckerTools, deptry_tool
from mcp_tools_py.code_checker_deptry.runners import DeptryMessage, DeptryResult
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.tool_context import ToolContext

_IMPL = "mcp_tools_py.checker_tools.deptry_tool.run_deptry_check_impl"


def _register_and_capture(context: ToolContext) -> dict[str, object]:
    """Register checker tools and capture the registered functions."""
    registered: dict[str, object] = {}

    def capture(func: Callable[..., object]) -> Callable[..., object]:
        registered[func.__name__] = func
        return func

    mock_mcp = MagicMock()
    mock_mcp.tool.return_value = capture

    checker = CheckerTools(context)
    deptry_tool.register(mock_mcp, checker)
    return registered


def test_deptry_not_available_message(tool_context: ToolContext) -> None:
    """When deptry is unavailable, the tool returns a not-available message."""
    tools = _register_and_capture(tool_context)

    with (
        patch.object(
            ToolContext,
            "is_tool_available",
            side_effect=lambda name: name != "deptry",
        ),
        patch(_IMPL) as mock_runner,
    ):
        result = tools["run_deptry_check"]()  # type: ignore[operator]

    assert "deptry is not available" in result
    mock_runner.assert_not_called()


def test_deptry_findings(tool_context: ToolContext) -> None:
    """When deptry finds issues, the formatted report is returned."""
    tools = _register_and_capture(tool_context)
    messages = [
        DeptryMessage(
            code="DEP001",
            message="'requests' imported but missing from the dependency definitions",
            module="requests",
            file="src/app.py",
            line=3,
            column=8,
        )
    ]

    with patch(_IMPL, return_value=DeptryResult(return_code=1, messages=messages)):
        result = tools["run_deptry_check"](  # type: ignore[operator]
            target_directories=["src"]
        )

    assert "DEP001" in result
    assert "src/app.py" in result


def test_deptry_error(tool_context: ToolContext) -> None:
    """When deptry returns an error, the error string is returned."""
    tools = _register_and_capture(tool_context)
    mock_result = DeptryResult(return_code=2, messages=[], error="deptry crashed")

    with patch(_IMPL, return_value=mock_result):
        result = tools["run_deptry_check"](  # type: ignore[operator]
            target_directories=["src"]
        )

    assert result == "deptry error: deptry crashed"


def test_deptry_clean(tool_context: ToolContext) -> None:
    """When deptry finds no issues, a clean message is returned."""
    tools = _register_and_capture(tool_context)

    with patch(_IMPL, return_value=DeptryResult(return_code=0, messages=[])):
        result = tools["run_deptry_check"](  # type: ignore[operator]
            target_directories=["src"]
        )

    assert result == "No deptry dependency issues found."


def test_deptry_default_targets_exclude_tests(tool_context: ToolContext) -> None:
    """Default targets are the source directories, without the test paths."""
    project_dir = tool_context.project_dir
    (project_dir / "src").mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [tool.setuptools.packages.find]
            where = ["src"]

            [tool.pytest.ini_options]
            testpaths = ["tests"]
            """),
        encoding="utf-8",
    )
    tools = _register_and_capture(tool_context)

    with patch(
        _IMPL, return_value=DeptryResult(return_code=0, messages=[])
    ) as mock_runner:
        tools["run_deptry_check"]()  # type: ignore[operator]

    assert mock_runner.call_args.kwargs["target_directories"] == ["src"]


def test_deptry_explicit_targets_passed_through(tool_context: ToolContext) -> None:
    """Explicit target_directories reach the runner unchanged."""
    tools = _register_and_capture(tool_context)

    with patch(
        _IMPL, return_value=DeptryResult(return_code=0, messages=[])
    ) as mock_runner:
        tools["run_deptry_check"](  # type: ignore[operator]
            target_directories=["lib", "tests"]
        )

    assert mock_runner.call_args.kwargs["target_directories"] == ["lib", "tests"]


def test_deptry_invalid_timeout(tool_context: ToolContext) -> None:
    """A non-positive timeout_seconds returns an error before running deptry."""
    tools = _register_and_capture(tool_context)

    with patch(_IMPL) as mock_runner:
        result = tools["run_deptry_check"](  # type: ignore[operator]
            target_directories=["src"], timeout_seconds=0
        )

    assert result.startswith("Error: ")
    mock_runner.assert_not_called()


@pytest.mark.integration
def test_deptry_real_run(tmp_path: Path) -> None:
    """Real deptry: clean on a stdlib import, DEP001 on an undeclared one."""
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent("""\
            [project]
            name = "p"
            version = "0"
            dependencies = []
            """),
        encoding="utf-8",
    )
    package = tmp_path / "src" / "p"
    package.mkdir(parents=True)
    module = package / "mod.py"
    module.write_text("import os\n", encoding="utf-8")
    environment = PythonEnvironment.resolve()
    context = ToolContext(
        project_dir=tmp_path,
        environment=environment,
        tool_environment=environment,
    )
    tools = _register_and_capture(context)

    clean = tools["run_deptry_check"](  # type: ignore[operator]
        target_directories=["src"]
    )
    assert clean == "No deptry dependency issues found."

    module.write_text("import os\nimport some_undeclared_pkg_xyz\n", encoding="utf-8")
    dirty = tools["run_deptry_check"](  # type: ignore[operator]
        target_directories=["src"]
    )
    assert "DEP001" in dirty
