"""
Data models for ruff analysis results.
"""

from typing import List, NamedTuple, Optional


class RuffMessage(NamedTuple):
    """Represents a single ruff violation message."""

    code: str
    message: str
    filename: str
    line: int
    column: int
    end_line: int
    end_column: int
    url: str
    fixable: bool
    noqa_row: int


class RuffResult(NamedTuple):
    """Represents the overall result of a ruff run."""

    return_code: int
    messages: List[RuffMessage]
    error: Optional[str] = None
    raw_output: Optional[str] = None
