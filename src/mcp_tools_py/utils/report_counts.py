"""Count and directory-split helpers shared by the checker reports."""

import re
from collections import Counter
from typing import Iterable

_OUTSIDE = "(outside)"
_ROOT = "(root)"


def plural(count: int, word: str) -> str:
    """Return ``count`` followed by ``word``, pluralised with ``s`` unless 1."""
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def _top_level_dir(path: str) -> str:
    """Map a project-relative path to its top-level directory.

    Returns ``(root)`` for files directly in the project root and ``(outside)``
    for absolute paths, ``..`` paths and pylint's ``Command line`` pseudo-path.
    """
    if path == "Command line":
        return _OUTSIDE
    normalized = path.replace("\\", "/")
    if (
        normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized)
        or normalized == ".."
        or normalized.startswith("../")
    ):
        return _OUTSIDE
    normalized = normalized.removeprefix("./")
    head, sep, _ = normalized.partition("/")
    return head if sep else _ROOT


def format_dir_split(paths: Iterable[str]) -> str:
    """Format per-top-level-directory counts, e.g. ``(src: 11, tests: 2)``.

    Ordered by count descending, ties alphabetical.
    """
    counts = Counter(_top_level_dir(path) for path in paths)
    items = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return "(" + ", ".join(f"{name}: {count}" for name, count in items) + ")"


def format_total_line(tool: str, issues: int, rules: int) -> str:
    """Format the report's total line, e.g. ``ruff found 3 issues across 2 rules``."""
    return f"{tool} found {plural(issues, 'issue')} across {plural(rules, 'rule')}"
