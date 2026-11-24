"""Pure extraction from a parsed pytest report, for the report-level reply sections."""

import ast
import os
import re
from dataclasses import dataclass
from pathlib import Path

from mcp_tools_py.code_checker_pytest.models import LogRecord, PytestReport, Test

_XDIST_HEADER = re.compile(r"\[gw\d+\]")
_SKIPPED_PREFIX = "Skipped: "


@dataclass(frozen=True)
class SkipKey:
    """Folding key of a skip entry, as pytest's _folded_skips uses it."""

    path: str
    lineno: int | None
    reason: str


def strip_xdist_header(longrepr: str | None) -> str | None:
    """Drop a leading "[gwN] ..." line; None when nothing remains.

    Args:
        longrepr: A longrepr text from the report, or None.

    Returns:
        The text without the xdist worker header, or None when it is empty.
    """
    if not longrepr:
        return None
    first, _, rest = longrepr.partition("\n")
    if _XDIST_HEADER.match(first):
        longrepr = rest
    return longrepr or None


def relative_path(path: str, root: str) -> str:
    """`path` relative to `root` in posix form; `path` as given when that is not possible.

    Args:
        path: A file path from the report.
        root: The report root directory.

    Returns:
        The relative posix path, or ``path`` unchanged for pseudo paths
        (``<frozen os>``), other drives and paths outside ``root``.
    """
    if path.startswith("<"):
        return path
    try:
        rel = os.path.relpath(path, root)
    except ValueError:
        return path
    return path if rel.startswith("..") else Path(rel).as_posix()


def format_log_record(record: LogRecord) -> str:
    """One record in pytest's default log format, then exc_text lines if any.

    Args:
        record: A captured log record.

    Returns:
        ``"LEVEL    logger:file:line message"``, followed by the exception text.
    """
    line = f"{record.levelname:<8} {record.name}:{record.filename}:{record.lineno} {record.msg}"
    if record.exc_text:
        line += "\n" + record.exc_text
    return line


def _parse_skip(longrepr: str | None, root: str) -> tuple[str, int, str] | None:
    """Read a skip longrepr ``str((path, lineno, 'Skipped: reason'))``.

    Args:
        longrepr: The skipped stage's or collector's longrepr.
        root: The report root directory.

    Returns:
        Relative path, line number and reason without the "Skipped: " prefix,
        or None when the text is not such a tuple.
    """
    text = strip_xdist_header(longrepr)
    if text is None:
        return None
    try:
        path, lineno, msg = ast.literal_eval(text)
    except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
        return None
    if not (isinstance(path, str) and isinstance(lineno, int) and isinstance(msg, str)):
        return None
    return relative_path(path, root), lineno, msg.removeprefix(_SKIPPED_PREFIX)


def _test_skip_key(test: Test, root: str) -> SkipKey | None:
    """Folding key of a skipped test, from its first skipped setup/call stage.

    Args:
        test: A test whose outcome is "skipped".
        root: The report root directory.

    Returns:
        The key, or None when no stage is skipped or its longrepr is unreadable.
    """
    for when, stage in (("setup", test.setup), ("call", test.call)):
        if stage is None or stage.outcome != "skipped":
            continue
        parsed = _parse_skip(stage.longrepr, root)
        if parsed is None:
            return None
        path, lineno, reason = parsed
        # pytest folds a module-level `pytestmark = pytest.mark.skip(...)` without line.
        if (
            when == "setup"
            and "skip" in test.keywords
            and "pytestmark" not in test.keywords
        ):
            return SkipKey(path, None, reason)
        return SkipKey(path, lineno, reason)
    return None


def folded_skips(report: PytestReport) -> list[tuple[int, SkipKey]]:
    """Skip entries of collectors, then tests, folded like pytest's _folded_skips.

    Args:
        report: The parsed pytest report.

    Returns:
        ``(count, key)`` pairs in first-seen order. Collector skips keep their
        line number; tests are read only when their outcome is "skipped"
        (an xfailed test's call stage is also "skipped" but not listed).
    """
    counts: dict[SkipKey, int] = {}
    for collector in report.collectors or []:
        if collector.outcome != "skipped":
            continue
        parsed = _parse_skip(collector.longrepr, report.root)
        if parsed is not None:
            key = SkipKey(*parsed)
            counts[key] = counts.get(key, 0) + 1
    for test in report.tests or []:
        if test.outcome != "skipped":
            continue
        test_key = _test_skip_key(test, report.root)
        if test_key is not None:
            counts[test_key] = counts.get(test_key, 0) + 1
    return [(count, key) for key, count in counts.items()]


def skip_lines(folded: list[tuple[int, SkipKey]]) -> list[str]:
    """Format folded skips the way pytest's -rs does.

    Args:
        folded: Entries from ``folded_skips``.

    Returns:
        ``"SKIPPED [3] tests/x.py:12: reason"`` per entry, or
        ``"SKIPPED [2] tests/x.py: reason"`` when the key has no line number.
    """
    lines = []
    for count, key in folded:
        location = key.path if key.lineno is None else f"{key.path}:{key.lineno}"
        lines.append(f"SKIPPED [{count}] {location}: {key.reason}")
    return lines


def module_skip_count(report: PytestReport) -> int:
    """Distinct node IDs of skipped collectors (module-level skips).

    Args:
        report: The parsed pytest report.

    Returns:
        The number of distinct skipped collector node IDs.
    """
    return len({c.nodeid for c in report.collectors or [] if c.outcome == "skipped"})


def skipped_count(report: PytestReport) -> int:
    """Skipped tests plus module-level skips, for the ``⏭️ Skipped`` count.

    Args:
        report: The parsed pytest report.

    Returns:
        ``summary.skipped`` (0 when missing) plus ``module_skip_count``.
    """
    return (report.summary.skipped or 0) + module_skip_count(report)
