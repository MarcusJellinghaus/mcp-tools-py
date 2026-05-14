"""Data models for ruff analysis results."""

from typing import NamedTuple


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
