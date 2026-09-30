"""Orchestration logic for running code formatters.

Provides a plain ``run_format_code()`` function that sequences formatter
runners (isort, black, ruff_imports, ruff_format).  In write mode the run
stops at the first failing step, unless that step reported unparsable files.
"""

from collections.abc import Callable
from pathlib import Path

from mcp_tools_py.formatter.black_runner import run_black
from mcp_tools_py.formatter.isort_runner import run_isort
from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.formatter.ruff_runner import run_ruff_format, run_ruff_imports
from mcp_tools_py.utils.project_config import (
    DEFAULT_CHECK_TIMEOUT,
    ToolName,
    read_pyproject_tool_tables,
)
from mcp_tools_py.utils.python_environment import PythonEnvironment

_BLACK_STEPS: list[str] = ["isort", "black"]
_RUFF_STEPS: list[str] = ["ruff_imports", "ruff_format"]

_VALID_STEPS: set[str] = {"isort", "black", "ruff_imports", "ruff_format"}

_STEP_RUNNERS: dict[str, Callable[..., FormatterResult]] = {
    "isort": run_isort,
    "black": run_black,
    "ruff_imports": run_ruff_imports,
    "ruff_format": run_ruff_format,
}

# A step is not a tool name. Both ruff steps map to tool `ruff`.
_STEP_TOOLS: dict[str, ToolName] = {
    "isort": "isort",
    "black": "black",
    "ruff_imports": "ruff",
    "ruff_format": "ruff",
}

_FORMATTER_STEPS: dict[str, list[str]] = {"black": _BLACK_STEPS, "ruff": _RUFF_STEPS}
_SET_KEY_HINT = 'Set [tool.mcp-tools-py] formatter = "black" or "ruff".'


def step_tool(step: str) -> ToolName:
    """Tool a step invokes — for availability, timeouts and line-length checks.

    Args:
        step: A valid formatter step name.

    Returns:
        The tool name the step runs.
    """
    return _STEP_TOOLS[step]


def resolve_steps(project_root: Path) -> list[str]:
    """Steps to run when the caller named none.

    ``[tool.mcp-tools-py] formatter`` wins when present; otherwise the
    formatter is detected from ``[tool.ruff.format]`` versus ``[tool.black]``.

    Args:
        project_root: Root project directory containing pyproject.toml.

    Returns:
        The formatter's steps, ordered by execution.

    Raises:
        ValueError: If no formatter is declared, or two are.
    """
    pyproject = project_root / "pyproject.toml"
    tools = read_pyproject_tool_tables(project_root)

    section = tools.get("mcp-tools-py")
    if isinstance(section, dict) and "formatter" in section:
        formatter = section["formatter"]
        if formatter in _FORMATTER_STEPS:
            return list(_FORMATTER_STEPS[formatter])
        raise ValueError(
            f"Invalid [tool.mcp-tools-py] formatter = {formatter!r} in "
            f'{pyproject}. Valid values are "black" and "ruff".'
        )

    ruff = tools.get("ruff")
    has_ruff = isinstance(ruff, dict) and isinstance(ruff.get("format"), dict)
    has_black = isinstance(tools.get("black"), dict)

    if has_ruff and has_black:
        raise ValueError(
            f"Cannot tell which formatter to use: {pyproject} declares both "
            f"[tool.black] and [tool.ruff.format]. {_SET_KEY_HINT}"
        )
    if not has_ruff and not has_black:
        raise ValueError(
            f"No formatter declared: {pyproject} has neither [tool.black] nor "
            f"[tool.ruff.format]. {_SET_KEY_HINT}"
        )
    return list(_RUFF_STEPS if has_ruff else _BLACK_STEPS)


def validate_steps(steps: list[str]) -> None:
    """Reject unknown step names and an empty list.

    Args:
        steps: Formatter step names to check.

    Raises:
        ValueError: If the list is empty or any step name is not in
            :data:`_VALID_STEPS`.
    """
    if not steps:
        raise ValueError(
            "Formatter steps must not be empty. Omit steps to use the "
            f"project's formatter, or name them: {sorted(_VALID_STEPS)}"
        )
    invalid = [s for s in steps if s not in _VALID_STEPS]
    if invalid:
        msg = (
            f"Invalid formatter steps: {invalid}. "
            f"Valid steps are: {sorted(_VALID_STEPS)}"
        )
        raise ValueError(msg)


def run_format_code(
    python_executable: str,
    project_root: Path,
    target_dirs: list[str],
    steps: list[str] | None = None,
    check_only: bool = False,
    timeouts: dict[str, int] | None = None,
    *,
    environment: PythonEnvironment | None = None,
) -> dict[str, FormatterResult]:
    """Run code formatters on the project.

    Args:
        python_executable: Deprecated. Accepted and ignored; the formatters
            run from `environment`.
        project_root: Root project directory.
        target_dirs: Directories to format.
        steps: Formatter steps to run in order.  None resolves them from the
            project's configuration via :func:`resolve_steps`.
        check_only: If True, only check formatting without modifying files.
        timeouts: Per-step timeout in seconds.  Each step gets its own budget;
            a missing step falls back to :data:`DEFAULT_CHECK_TIMEOUT`.
        environment: Environment whose formatter console scripts run. None
            means mcp-tools-py's own environment.

    Returns:
        Dict keyed by step name with :class:`FormatterResult` values,
        ordered by execution.

    Raises:
        ValueError: If no formatter can be resolved, or the steps are empty
            or unknown.  Raised by :func:`resolve_steps` or
            :func:`validate_steps` and propagated to callers.
    """  # noqa: DOC502 - propagated from resolve_steps/validate_steps.
    resolved_steps = resolve_steps(project_root) if steps is None else steps
    validate_steps(resolved_steps)

    results: dict[str, FormatterResult] = {}
    for step in resolved_steps:
        runner = _STEP_RUNNERS[step]
        result = runner(
            python_executable,
            target_dirs,
            str(project_root),
            check_only,
            (timeouts or {}).get(step, DEFAULT_CHECK_TIMEOUT),
            environment=environment,
        )
        results[step] = result
        if not result.success and not check_only and not result.unparsable_files:
            break

    return results
