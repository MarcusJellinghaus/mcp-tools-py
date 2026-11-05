"""Coverage support for run_pytest_check.

The pytest-cov flags built here are appended after the user's extra_args, so
the trailing ``--cov-fail-under=0`` wins over any threshold the target project
configures or the user passes: coverage is reported, never enforced.
"""

import hashlib
import json
import os
import posixpath
import shlex
from collections.abc import Iterable
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
MAX_ZERO_COVERAGE_ROWS = 15
MODULE_LEVEL = "<module level>"
ROOT_ROW = "(root)"


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
    parts = []
    m_value, m_from_addopts = _effective_option(
        "-m", cleaned_args, addopts, " and ".join(markers or [])
    )
    if m_value:
        parts.append(
            f"addopts -m '{m_value}'" if m_from_addopts else f"markers '{m_value}'"
        )

    k_value, k_from_addopts = _effective_option("-k", cleaned_args, addopts)
    if k_value:
        parts.append(f"addopts -k '{k_value}'" if k_from_addopts else f"-k '{k_value}'")

    if path_args:
        parts.append("paths " + ", ".join(path_args))

    if not parts:
        return "selection: full suite (no markers, -k or path arguments)"
    return "selection: " + "; ".join(parts)


def selection_identity(
    markers: list[str] | None,
    cleaned_args: list[str],
    path_args: list[str],
    addopts: str | None,
    env_vars: dict[str, str] | None,
) -> str:
    """Build the value that tells whether two runs selected the same tests.

    Order doesn't matter and ``--cov*`` args don't count. The env is hashed,
    because the identity is saved to disk.

    Args:
        markers: The ``markers`` parameter of run_pytest_check.
        cleaned_args: The sanitized extra_args.
        path_args: The path arguments among cleaned_args.
        addopts: The target project's pytest ``addopts``, if any.
        env_vars: The caller's env vars, if any.

    Returns:
        A JSON string, to compare with ``==``.
    """
    m_value, _ = _effective_option(
        "-m", cleaned_args, addopts, " and ".join(sorted(markers or []))
    )
    k_value, _ = _effective_option("-k", cleaned_args, addopts)

    rest = []
    tokens = iter(cleaned_args)
    for token in tokens:
        if token in ("-m", "-k"):
            next(tokens, None)
        elif not token.startswith(("-m", "-k", "--cov")) and token not in path_args:
            rest.append(token)

    env = ""
    if env_vars:
        env = hashlib.sha256(
            json.dumps(sorted(env_vars.items())).encode("utf-8")
        ).hexdigest()
    return json.dumps([m_value, k_value, sorted(path_args), sorted(rest), env])


def _effective_option(
    flag: str, cleaned_args: list[str], addopts: str | None, default: str = ""
) -> tuple[str | None, bool]:
    """Find the value of ``-m`` or ``-k`` that pytest ends up using.

    Args:
        flag: The short option to look up.
        cleaned_args: The sanitized extra_args.
        addopts: The target project's pytest ``addopts``, if any.
        default: The value the command line has when cleaned_args has none.

    Returns:
        The value, or None when there is none, and whether it comes from
        addopts.
    """
    # runners.py puts the markers -m before extra_args, so an -m there wins.
    if value := _option_value(cleaned_args, flag) or default:
        return value, False
    try:
        add = shlex.split(addopts or "")
    except ValueError:
        add = []
    if add_value := _option_value(add, flag):
        return add_value, True
    return None, False


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


def norm_path(path: str) -> str:
    """Normalize a path for comparing, as coverage keys use backslashes on Windows.

    Returns:
        The path with forward slashes and no redundant components.
    """
    return posixpath.normpath(path.replace("\\", "/"))


def percent_covered(summaries: Iterable[dict[str, Any]]) -> float:
    """Compute the covered percentage of file summaries the way coverage does.

    Args:
        summaries: The ``summary`` entries of a coverage JSON's files. The
            branch keys are absent without ``branch = true``.

    Returns:
        The percentage over lines and branches; 100.0 when there are none.
    """
    covered = total = 0
    for summary in summaries:
        covered += summary.get("covered_lines", 0) + summary.get("covered_branches", 0)
        total += summary.get("num_statements", 0) + summary.get("num_branches", 0)
    return 100.0 * covered / total if total else 100.0


def _common_prefix(files: dict[str, Any]) -> tuple[str, ...]:
    """Find the leading directories shared by all files except __init__.py.

    Ignoring __init__.py gives a layout with ``src/__init__.py`` one table row
    per subpackage instead of a single row.

    Returns:
        The shared directory names; empty when there are none.
    """
    directories = [
        parts[:-1]
        for parts in (norm_path(path).split("/") for path in files)
        if parts[-1] != "__init__.py"
    ]
    prefix = []
    for names in zip(*directories):
        if len(set(names)) > 1:
            break
        prefix.append(names[0])
    return tuple(prefix)


def _package_table(files: dict[str, Any]) -> list[str]:
    """Render one row per top-level package, sorted by missing statements.

    Args:
        files: The ``files`` entry of the coverage JSON.

    Returns:
        The table's header and rows; empty when no row has statements.
    """
    prefix = _common_prefix(files)
    packages: dict[str, list[dict[str, Any]]] = {}
    for path, entry in files.items():
        parts = tuple(norm_path(path).split("/"))
        rest = parts[len(prefix) :] if parts[: len(prefix)] == prefix else ()
        name = rest[0] if len(rest) > 1 else ROOT_ROW
        packages.setdefault(name, []).append(entry.get("summary", {}))

    rows = []
    for name, summaries in packages.items():
        statements = sum(summary.get("num_statements", 0) for summary in summaries)
        if statements:
            missing = sum(summary.get("missing_lines", 0) for summary in summaries)
            rows.append((-missing, name, statements, percent_covered(summaries)))
    if not rows:
        return []

    width = max(len(row[1]) for row in rows)
    return [
        "by package (statements, covered %):",
        *(
            f"    {name.ljust(width)}  {statements:>6} {percent:>3.0f}%"
            for _, name, statements, percent in sorted(rows)
        ),
    ]


def _is_filesystem_root(directory: tuple[str, ...]) -> bool:
    """Tell whether split path components name ``/`` or a drive such as ``C:``.

    Returns:
        True for a filesystem root.
    """
    return len(directory) == 1 and (not directory[0] or directory[0].endswith(":"))


def _zero_coverage_rows(files: dict[str, Any]) -> list[tuple[str, int]]:
    """Collapse modules with nothing covered into their uncovered directories.

    A module's row is its top-most ancestor with no covered file below it, as
    ``a/b/``, never above the common prefix. A module with no such ancestor, or
    outside the prefix, gets its own row. Files with no statements are ignored.

    Args:
        files: The ``files`` entry of the coverage JSON.

    Returns:
        (label, missing statements) rows, sorted by missing statements.
    """
    prefix = _common_prefix(files)
    blocked: set[tuple[str, ...]] = set()
    zero = []
    for path, entry in files.items():
        summary = entry.get("summary", {})
        parts = tuple(norm_path(path).split("/"))
        if summary.get("covered_lines", 0) > 0:
            blocked.update(parts[:depth] for depth in range(1, len(parts)))
        elif summary.get("num_statements", 0):
            zero.append((parts, summary.get("missing_lines", 0)))

    rows: dict[str, int] = {}
    for parts, missing in zero:
        label = "/".join(parts)
        if parts[: len(prefix)] == prefix:
            for depth in range(max(len(prefix), 1), len(parts)):
                ancestor = parts[:depth]
                if ancestor not in blocked and not _is_filesystem_root(ancestor):
                    label = "/".join(ancestor) + "/"
                    break
        rows[label] = rows.get(label, 0) + missing
    return sorted(rows.items(), key=lambda row: (-row[1], row[0]))


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

    The totals are summed from ``files``, never read from the report's
    ``totals``. Modules with gaps are ranked by absolute missing statements;
    modules with nothing covered are listed separately, collapsed by directory,
    with no cause attributed.

    Args:
        data: The coverage JSON report.
        selection: The line from selection_line.
        max_modules: How many modules the gap ranking details; 0 shows only
            the overview.
        fail_under: The project's threshold; None when it could not be read.
        failed_collectors: How many collectors failed in the run.
        failed_tests: How many tests failed or errored in the run.
        generic_warning: Whether the run errored with neither count to show.

    Returns:
        The multi-line digest.
    """
    max_modules = max(0, max_modules)
    files: dict[str, Any] = data.get("files", {})
    summaries = [entry.get("summary", {}) for entry in files.values()]

    lines = [
        *_warning_lines(failed_collectors, failed_tests, generic_warning),
        f"{percent_covered(summaries):.1f}%  "
        f"{sum(summary.get('num_statements', 0) for summary in summaries)} stmts  "
        f"{sum(summary.get('missing_lines', 0) for summary in summaries)} missed  |  "
        f"{len(files)} modules measured",
        selection,
    ]
    if fail_under is None:
        lines.append("fail_under: could not be read from the coverage config")
    elif fail_under > 0:
        lines.append(
            f"fail_under={fail_under:g} is configured; not applied to this run"
        )

    if table := _package_table(files):
        lines += ["", *table]

    zero = []
    gaps = []
    for path, entry in files.items():
        summary = entry.get("summary", {})
        missing = summary.get("missing_lines", 0)
        if summary.get("covered_lines", 0) == 0 and summary.get("num_statements", 0):
            zero.append(path)
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
        rows = _zero_coverage_rows(files)
        lines += [
            f"    {label} ({missing} missing statements)"
            for label, missing in rows[:MAX_ZERO_COVERAGE_ROWS]
        ]
        if len(rows) > MAX_ZERO_COVERAGE_ROWS:
            lines.append(f"    … and {len(rows) - MAX_ZERO_COVERAGE_ROWS} more")

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
