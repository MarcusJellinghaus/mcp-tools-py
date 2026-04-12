"""Data models for formatter results."""

import dataclasses


@dataclasses.dataclass
class FormatterResult:
    """Result of running a code formatter.

    Attributes:
        output: Raw text output (for MCP display).
        success: True when return_code == 0.
        files_changed: Parsed file paths that were (or would be) changed.
    """

    output: str
    success: bool
    files_changed: list[str]
