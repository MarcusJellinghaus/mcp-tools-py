"""Pure extraction from a parsed pytest report, for the report-level reply sections."""

import os
import re
from pathlib import Path

from mcp_tools_py.code_checker_pytest.models import LogRecord

_XDIST_HEADER = re.compile(r"\[gw\d+\]")


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
