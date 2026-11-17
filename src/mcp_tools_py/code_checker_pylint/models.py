"""Data models for pylint analysis results."""

from enum import Enum
from typing import NamedTuple


class PylintMessageType(Enum):
    """Categories for Pylint message types."""

    CONVENTION = "convention"
    REFACTOR = "refactor"
    WARNING = "warning"
    ERROR = "error"
    FATAL = "fatal"


class PylintMessage(NamedTuple):
    """Represents a single Pylint message."""

    type: str
    module: str
    obj: str
    line: int
    column: int
    # endLine and endColumn missing
    path: str
    symbol: str
    message: str
    message_id: str


class PylintResult(NamedTuple):
    """Represents the overall result of a Pylint run."""

    return_code: int
    messages: list[PylintMessage]
    error: str | None = None  # Capture any execution errors
    raw_output: str | None = None  # Capture raw output from pylint

    def get_message_ids(self) -> set[str]:
        """Returns a set of all unique message IDs."""
        return {message.message_id for message in self.messages}

    def get_messages_filtered_by_message_id(
        self, message_id: str
    ) -> list[PylintMessage]:
        """Returns a list of messages filtered by the given message ID."""
        return [
            message for message in self.messages if message.message_id == message_id
        ]
