"""Orchestration logic for running code formatters.

Provides a plain ``run_format_code()`` function that sequences formatter
runners (isort, black) with fail-fast behaviour.
"""

from collections.abc import Callable
from pathlib import Path

from mcp_tools_py.formatter.black_runner import run_black
from mcp_tools_py.formatter.isort_runner import run_isort
from mcp_tools_py.formatter.models import FormatterResult

DEFAULT_STEPS: list[str] = ["isort", "black"]

_VALID_STEPS: set[str] = {"isort", "black"}

_STEP_RUNNERS: dict[str, Callable[..., FormatterResult]] = {
    "isort": run_isort,
    "black": run_black,
}


def run_format_code(
    python_executable: str,
    project_root: Path,
    target_dirs: list[str],
    steps: list[str] | None = None,
    check_only: bool = False,
) -> dict[str, FormatterResult]:
    """Run code formatters on the project.

    Args:
        python_executable: Path to the Python executable.
        project_root: Root project directory.
        target_dirs: Directories to format.
        steps: Formatter steps to run in order.  Defaults to
            ``["isort", "black"]``.
        check_only: If True, only check formatting without modifying files.

    Returns:
        Dict keyed by step name with :class:`FormatterResult` values,
        ordered by execution.

    Raises:
        ValueError: If any step name is not in :data:`_VALID_STEPS`.
    """
    resolved_steps = steps or DEFAULT_STEPS

    invalid = [s for s in resolved_steps if s not in _VALID_STEPS]
    if invalid:
        msg = (
            f"Invalid formatter steps: {invalid}. "
            f"Valid steps are: {sorted(_VALID_STEPS)}"
        )
        raise ValueError(msg)

    results: dict[str, FormatterResult] = {}
    for step in resolved_steps:
        runner = _STEP_RUNNERS[step]
        result = runner(python_executable, target_dirs, str(project_root), check_only)
        results[step] = result
        if not result.success and not check_only:
            break

    return results
