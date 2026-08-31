"""Data models for formatter results."""

import dataclasses


@dataclasses.dataclass
class FormatterResult:
    """Result of running a code formatter.

    Attributes:
        output: Raw text output (for MCP display).
        success: True when the formatter exited 0 and processed every target
            file.
        files_changed: Parsed file paths that were (or would be) changed.
        unparsable_files: Paths the formatter reported it could not read. A
            non-empty list means the run was incomplete.
    """

    output: str
    success: bool
    files_changed: list[str]
    unparsable_files: list[str] = dataclasses.field(default_factory=list)
