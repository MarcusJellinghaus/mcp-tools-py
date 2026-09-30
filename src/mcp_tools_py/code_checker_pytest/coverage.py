"""Coverage support for run_pytest_check.

The pytest-cov flags built here are appended after the user's extra_args, so
the trailing ``--cov-fail-under=0`` wins over any threshold the target project
configures or the user passes: coverage is reported, never enforced.
"""

import json
import os
from typing import Any

from mcp_tools_py.utils.environment_info import PROBE_TIMEOUT_SECONDS
from mcp_tools_py.utils.file_utils import read_file
from mcp_tools_py.utils.subprocess_runner import execute_command

COVERAGE_JSON = "coverage.json"
COVERAGE_DATA = ".coverage"

_FAIL_UNDER_SCRIPT = "import coverage; print(coverage.Coverage().config.fail_under)"


def coverage_args(
    sources: list[str], temp_dir: str
) -> tuple[list[str], dict[str, str]]:
    """Pytest flags and env vars for one coverage run writing into temp_dir.

    Args:
        sources: Directories to measure, one ``--cov`` flag each.
        temp_dir: Directory receiving the JSON report and the data file.

    Returns:
        The pytest flags, ending with ``--cov-fail-under=0``, and the env
        vars to add. ``COVERAGE_FILE`` names a file inside temp_dir so xdist
        data fragments stay inside it too.
    """
    args = [f"--cov={source}" for source in sources]
    args += [
        f"--cov-report=json:{os.path.join(temp_dir, COVERAGE_JSON)}",
        "--cov-fail-under=0",
    ]
    env = {"COVERAGE_FILE": os.path.join(temp_dir, COVERAGE_DATA)}
    return args, env


def read_coverage_report(temp_dir: str) -> dict[str, Any] | None:
    """Load the coverage JSON from temp_dir, or None when absent or unparsable."""
    try:
        report = json.loads(read_file(os.path.join(temp_dir, COVERAGE_JSON)))
    except (OSError, ValueError):
        return None
    return report if isinstance(report, dict) else None


def read_fail_under(interpreter: str, project_dir: str) -> float | None:
    """Effective ``fail_under`` of the project, read in the target interpreter.

    Runs with ``cwd=project_dir`` because coverage resolves its configuration
    relative to the working directory.

    Returns:
        The threshold; 0.0 when none is configured; None when it could not
        be read.
    """
    result = execute_command(
        [interpreter, "-c", _FAIL_UNDER_SCRIPT],
        cwd=project_dir,
        timeout_seconds=PROBE_TIMEOUT_SECONDS,
    )
    if result.timed_out or result.execution_error or result.return_code != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None
