"""Shared test utilities and fixtures."""

from typing import Iterator

import pytest

from mcp_tools_py.utils.environment_info import get_environment_info
from mcp_tools_py.utils.subprocess_runner import CommandResult


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


@pytest.fixture(autouse=True)
def _clear_environment_info_cache() -> Iterator[None]:
    """Keep the process-wide probe cache from leaking between tests.

    The lru_cache lives on the module, not on any server, and an xdist worker
    runs many modules per process.
    """
    get_environment_info.cache_clear()
    yield
    get_environment_info.cache_clear()
