"""Data models for bandit security analysis results."""

from typing import NamedTuple


class BanditMessage(NamedTuple):
    """Represents a single bandit security finding."""

    test_id: str
    test_name: str
    issue_severity: str
    issue_confidence: str
    issue_text: str
    filename: str
    line_number: int
    more_info: str
    cwe_id: int
    cwe_link: str


class BanditResult(NamedTuple):
    """Represents the complete bandit execution result."""

    return_code: int
    messages: list[BanditMessage]
    errors: list[str]
    error: str | None = None
    raw_output: str | None = None
