"""Coverage support for run_pytest_check.

The pytest-cov flags built here are appended after the user's extra_args, so
the trailing ``--cov-fail-under=0`` wins over any threshold the target project
configures or the user passes: coverage is reported, never enforced.
"""

import json
import os
import shlex
from typing import Any, TypedDict

from mcp_tools_py.code_checker_pytest.models import PytestReport
from mcp_tools_py.code_checker_pytest.reporting import failed_collector_count, plural
from mcp_tools_py.code_checker_pytest.verdict import RunStatus, RunVerdict
from mcp_tools_py.utils.environment_info import PROBE_TIMEOUT_SECONDS
from mcp_tools_py.utils.file_utils import read_file
from mcp_tools_py.utils.subprocess_runner import execute_command

COVERAGE_JSON = "coverage.json"
COVERAGE_DATA = ".coverage"

_FAIL_UNDER_SCRIPT = "import coverage; print(coverage.Coverage().config.fail_under)"

MAX_FUNCTIONS_PER_MODULE = 3
MAX_RANGES_PER_FUNCTION = 5
MODULE_LEVEL = "<module level>"


class RunOutcome(TypedDict):
    """The failure state of one pytest run, as the digest qualifies it."""

    failed_collectors: int
    failed_tests: int
    generic_warning: bool


def run_outcome(report: PytestReport | None, verdict: RunVerdict) -> RunOutcome:
    """Reduce a pytest run to the counts and flag that qualify its coverage.

    Args:
        report: The parsed pytest report, if any.
        verdict: The verdict of the run.

    Returns:
        The failed-collector and failed-test counts, and whether the run is an
        ERROR with neither to show for it. All zero without a report.
    """
    if report is None:
        return RunOutcome(failed_collectors=0, failed_tests=0, generic_warning=False)
    failed_collectors = failed_collector_count(report)
    # classify_run returns FAILED on summary.error alone, so errors count here.
    failed_tests = (report.summary.failed or 0) + (report.summary.error or 0)
    return RunOutcome(
        failed_collectors=failed_collectors,
        failed_tests=failed_tests,
        generic_warning=verdict.status is RunStatus.ERROR
        and failed_collectors == 0
        and failed_tests == 0,
    )


def no_report_message(failed_collectors: int) -> str:
    """Render the reply for a run that left no coverage report to digest.

    Args:
        failed_collectors: The failed-collector count of the run.

    Returns:
        The one-line message, naming the count when there is one.
    """
    message = "Coverage report was not produced."
    if not failed_collectors:
        return message
    noun = plural(failed_collectors, "collector")
    return f"{message} {failed_collectors} {noun} failed."


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
    """Load the coverage JSON report written to temp_dir.

    Returns:
        The parsed report, or None when it is absent or unparsable.
    """
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


def selection_line(
    markers: list[str] | None,
    cleaned_args: list[str],
    path_args: list[str],
    addopts: str | None,
) -> str:
    """One line naming everything that narrowed the run, or saying nothing did.

    The command line overrides ``addopts`` (pytest prepends addopts), so the
    effective ``-m`` and ``-k`` are reported, labelled with their source.

    Args:
        markers: The ``markers`` parameter of run_pytest_check.
        cleaned_args: The sanitized extra_args.
        path_args: The path arguments among cleaned_args.
        addopts: The target project's pytest ``addopts``, if any.

    Returns:
        A line starting with ``selection: ``.
    """
    try:
        add = shlex.split(addopts or "")
    except ValueError:
        add = []

    parts = []
    # runners.py puts the markers -m before extra_args, so an -m there wins.
    cmd_m = _option_value(cleaned_args, "-m") or (
        " and ".join(markers) if markers else None
    )
    if cmd_m:
        parts.append(f"markers '{cmd_m}'")
    elif add_m := _option_value(add, "-m"):
        parts.append(f"addopts -m '{add_m}'")

    if cmd_k := _option_value(cleaned_args, "-k"):
        parts.append(f"-k '{cmd_k}'")
    elif add_k := _option_value(add, "-k"):
        parts.append(f"addopts -k '{add_k}'")

    if path_args:
        parts.append("paths " + ", ".join(path_args))

    if not parts:
        return "selection: full suite (no markers, -k or path arguments)"
    return "selection: " + "; ".join(parts)


def _option_value(tokens: list[str], flag: str) -> str | None:
    """Find the value of a short option (`-m X` or `-mX`) in tokens.

    Returns:
        The last value given, as pytest keeps the last; None when absent.
    """
    value = None
    for i, token in enumerate(tokens):
        if token == flag:
            if i + 1 < len(tokens):
                value = tokens[i + 1]
        elif token.startswith(flag):
            value = token[len(flag) :]
    return value


def _warning_lines(
    failed_collectors: int, failed_tests: int, generic_warning: bool
) -> list[str]:
    """Render the lines that qualify a digest, each only when it applies.

    Returns:
        The collector, test and generic warning lines, in that order.
    """
    lines = []
    if failed_collectors:
        noun = plural(failed_collectors, "collector")
        lines.append(
            f"⚠ {failed_collectors} {noun} failed — "
            "coverage below reflects a partial run"
        )
    if failed_tests:
        noun = plural(failed_tests, "test")
        lines.append(
            f"⚠ {failed_tests} {noun} failed — "
            "coverage below comes from a run with failures"
        )
    if generic_warning:
        lines.append(
            "⚠ the pytest run reported an error — coverage below may be incomplete"
        )
    return lines


def format_coverage_digest(
    data: dict[str, Any],
    selection: str,
    max_modules: int = 10,
    fail_under: float | None = 0.0,
    failed_collectors: int = 0,
    failed_tests: int = 0,
    generic_warning: bool = False,
) -> str:
    """Render the coverage JSON as the digest appended to the pytest reply.

    Modules with gaps are ranked by absolute missing statements; modules with
    nothing covered are listed separately, with no cause attributed.

    Args:
        data: The coverage JSON report.
        selection: The line from selection_line.
        max_modules: How many modules to detail in each list.
        fail_under: The project's threshold; None when it could not be read.
        failed_collectors: How many collectors failed in the run.
        failed_tests: How many tests failed or errored in the run.
        generic_warning: Whether the run errored with neither count to show.

    Returns:
        The multi-line digest.
    """
    max_modules = max(0, max_modules)
    totals = data.get("totals", {})
    files: dict[str, Any] = data.get("files", {})

    lines = [
        *_warning_lines(failed_collectors, failed_tests, generic_warning),
        f"{totals.get('percent_covered', 0.0):.1f}%  "
        f"{totals.get('num_statements', 0)} stmts  "
        f"{totals.get('missing_lines', 0)} missed  |  "
        f"{len(files)} modules measured",
        selection,
    ]
    if fail_under is None:
        lines.append("fail_under: could not be read from the coverage config")
    elif fail_under > 0:
        lines.append(
            f"fail_under={fail_under:g} is configured; not applied to this run"
        )

    zero = []
    gaps = []
    for path, entry in files.items():
        summary = entry.get("summary", {})
        missing = summary.get("missing_lines", 0)
        if summary.get("covered_lines", 0) == 0 and summary.get("num_statements", 0):
            zero.append((path, missing))
        elif missing > 0:
            gaps.append((path, missing))
    gaps.sort(key=lambda gap: (-gap[1], gap[0]))

    if not gaps and not zero:
        lines += ["", "No uncovered statements in the measured modules."]

    degraded = False
    if gaps[:max_modules]:
        lines.append("")
    for path, missing in gaps[:max_modules]:
        entry = files[path]
        percent = entry.get("summary", {}).get("percent_covered", 0.0)
        lines.append(f"{path}  {missing} missing  ({percent:.0f}%)")
        if "functions" not in entry:
            degraded = True
            lines.append("    " + _capped_ranges(entry.get("missing_lines", [])))
            continue
        regions = sorted(
            (
                (name or MODULE_LEVEL, region.get("missing_lines", []))
                for name, region in entry["functions"].items()
                if region.get("missing_lines")
            ),
            key=lambda region: (-len(region[1]), region[0]),
        )
        shown = regions[:MAX_FUNCTIONS_PER_MODULE]
        width = max((len(name) for name, _ in shown), default=0)
        for name, region_lines in shown:
            lines.append(f"    {name.ljust(width)}  {_capped_ranges(region_lines)}")
        if len(regions) > len(shown):
            lines.append(f"    … {len(regions) - len(shown)} more functions")
    if degraded:
        lines.append(
            "Per-function detail needs coverage >= 7.6.0; showing file-level ranges."
        )

    if zero:
        lines += [
            "",
            f"{len(zero)} modules have no covered statements in this selection:",
        ]
        lines += [
            f"    {path} ({missing} missing statements)"
            for path, missing in zero[:max_modules]
        ]
        if len(zero) > max_modules:
            lines.append(f"    … and {len(zero) - max_modules} more")

    if len(gaps) > max_modules:
        lines += [
            "",
            f"{len(gaps) - max_modules} further modules have gaps "
            "(use max_modules to see more).",
        ]
    return "\n".join(lines)


def _capped_ranges(lines: list[int]) -> str:
    """Format line numbers as ranges, capped at MAX_RANGES_PER_FUNCTION.

    Returns:
        The comma-separated ranges, ending in an ellipsis if cut.
    """
    ranges = _ranges(sorted(lines))
    shown = ", ".join(ranges[:MAX_RANGES_PER_FUNCTION])
    return shown + ", …" if len(ranges) > MAX_RANGES_PER_FUNCTION else shown


def _ranges(lines: list[int]) -> list[str]:
    """Collapse sorted line numbers into consecutive runs.

    Returns:
        One "a-b" string per run, or "a" for a single line.
    """
    result = []
    start = end = None
    for line in lines:
        if end is not None and line == end + 1:
            end = line
            continue
        if start is not None:
            result.append(f"{start}-{end}" if end != start else f"{start}")
        start = end = line
    if start is not None:
        result.append(f"{start}-{end}" if end != start else f"{start}")
    return result
