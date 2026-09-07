"""Shared test utilities and fixtures."""

from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, patch

import pytest

from mcp_tools_py.utils.environment_info import (
    PROBED_MODULES,
    EnvironmentInfo,
    get_environment_info,
)
from mcp_tools_py.utils.python_environment import PythonEnvironment
from mcp_tools_py.utils.subprocess_runner import CommandResult
from mcp_tools_py.utils.tool_context import CONSOLE_SCRIPT_TOOLS, ToolContext
from tests.test_tool_availability._helpers import _dummy_python

_GET_ENVIRONMENT_INFO = "mcp_tools_py.utils.tool_context.get_environment_info"


def make_command_result(
    return_code: int = 0,
    stdout: str = "",
    stderr: str = "",
    execution_error: str | None = None,
    timed_out: bool = False,
) -> CommandResult:
    """Helper to build a CommandResult for mocking."""
    return CommandResult(
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
        timed_out=timed_out,
        execution_error=execution_error,
    )


def make_environment_info(
    version: str = "3.11.9",
    distributions: dict[str, str] | None = None,
    **importable: bool,
) -> EnvironmentInfo:
    """Build a successful probe result, importable unless stated otherwise.

    Args:
        version: Python version the probe reports.
        distributions: Lowercased distribution name -> installed version.
        importable: Per-module overrides of the default "yes, importable".

    Returns:
        An EnvironmentInfo with no error.
    """
    reported = {module: True for module in PROBED_MODULES}
    reported.update(importable)
    return EnvironmentInfo(
        version=version,
        sys_path=(),
        distributions=distributions or {},
        importable=reported,
    )


@pytest.fixture
def tool_context(tmp_path: Path) -> Iterator[ToolContext]:
    """A ToolContext over a tmp_path environment where every tool is available.

    Console-script availability is a real filesystem check against the pinned
    script directory, so a test makes one unavailable by deleting its binary.
    Module availability is answered by the patched probe.
    """
    interpreter = _dummy_python(tmp_path, *sorted(CONSOLE_SCRIPT_TOOLS))
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    context = ToolContext(
        project_dir=project_dir,
        environment=PythonEnvironment(Path(interpreter)),
    )
    with patch(_GET_ENVIRONMENT_INFO, return_value=make_environment_info()):
        yield context


@pytest.fixture
def all_modules_importable() -> Iterator[MagicMock]:
    """Answer every module-tool availability question yes, without probing."""
    with patch(_GET_ENVIRONMENT_INFO, return_value=make_environment_info()) as patched:
        yield patched


@pytest.fixture(autouse=True)
def _clear_environment_info_cache() -> Iterator[None]:
    """Keep the process-wide probe cache from leaking between tests.

    The lru_cache lives on the module, not on any server, and an xdist worker
    runs many modules per process.
    """
    get_environment_info.cache_clear()
    yield
    get_environment_info.cache_clear()
