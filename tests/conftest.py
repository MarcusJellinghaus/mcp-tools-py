"""Shared test utilities and fixtures."""

from mcp_coder_utils.subprocess_runner import CommandResult


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
