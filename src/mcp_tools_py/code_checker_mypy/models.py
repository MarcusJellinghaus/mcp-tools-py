"""Data models for mypy type checking results."""

from enum import Enum
from typing import NamedTuple


class MypySeverity(Enum):
    """Severity levels for mypy messages."""

    ERROR = "error"
    WARNING = "warning"
    NOTE = "note"


class MypyMessage(NamedTuple):
    """Represents a single mypy diagnostic message."""

    file: str
    line: int
    column: int
    severity: str
    message: str
    code: str | None = None  # e.g., "[arg-type]", "[import]"


class MypyResult(NamedTuple):
    """Represents the complete mypy execution result."""

    return_code: int
    messages: list[MypyMessage]
    error: str | None = None
    raw_output: str | None = None
    files_checked: int | None = None
    errors_found: int | None = None

    def get_error_codes(self) -> set[str]:
        """Returns unique error codes from messages."""
        return {msg.code for msg in self.messages if msg.code}

    def get_messages_by_severity(self, severity: str) -> list[MypyMessage]:
        """Filter messages by severity level."""
        return [msg for msg in self.messages if msg.severity == severity]
