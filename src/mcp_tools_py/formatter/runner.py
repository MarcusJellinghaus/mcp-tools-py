"""Orchestration logic for running code formatters.

Provides a plain ``run_format_code()`` function that sequences formatter
runners (isort, black) with fail-fast behaviour.
"""

from collections.abc import Callable
from pathlib import Path

from mcp_tools_py.formatter.black_runner import run_black
from mcp_tools_py.formatter.isort_runner import run_isort
from mcp_tools_py.formatter.models import FormatterResult
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT

DEFAULT_STEPS: list[str] = ["isort", "black"]

_VALID_STEPS: set[str] = {"isort", "black"}

_STEP_RUNNERS: dict[str, Callable[..., FormatterResult]] = {
    "isort": run_isort,
    "black": run_black,
}


def validate_steps(steps: list[str]) -> None:
    """Reject step names that are not known formatters.

    Args:
        steps: Formatter step names to check.

    Raises:
        ValueError: If any step name is not in :data:`_VALID_STEPS`.
    """
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
) -> dict[str, FormatterResult]:
    """Run code formatters on the project.

    Args:
        python_executable: Path to the Python executable.
        project_root: Root project directory.
        target_dirs: Directories to format.
        steps: Formatter steps to run in order.  Defaults to
            ``["isort", "black"]``.
        check_only: If True, only check formatting without modifying files.
        timeouts: Per-step timeout in seconds.  Each step gets its own budget;
            a missing step falls back to :data:`DEFAULT_CHECK_TIMEOUT`.

    Returns:
        Dict keyed by step name with :class:`FormatterResult` values,
        ordered by execution.

    Raises:
        ValueError: If any step name is not in :data:`_VALID_STEPS`.
            Raised by :func:`validate_steps` and propagated to callers.
    """  # noqa: DOC502 - propagated from validate_steps, not raised here.
    resolved_steps = steps or DEFAULT_STEPS
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
        )
        results[step] = result
        if not result.success and not check_only:
            break

    return results
