"""Helpers shared by the formatter runners."""

from mcp_tools_py.utils.python_environment import PythonEnvironment


def formatter_binary(
    name: str, environment: PythonEnvironment | None = None
) -> str | None:
    """Locate `name`'s console script, defaulting to mcp-tools-py's own environment.

    Args:
        name: Console script to look for, e.g. ``"black"``.
        environment: Environment to search. None means mcp-tools-py's own,
            resolved afresh on each call.

    Returns:
        Path to the console script, or None when it is not there.
    """
    env = environment or PythonEnvironment.resolve()
    binary = env.binary(name)
    return str(binary) if binary is not None else None
