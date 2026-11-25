"""Data models for pytest test results and reports."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Crash:
    """Crash details from a pytest failure."""

    path: str
    lineno: int
    message: str


@dataclass
class TracebackEntry:
    """Single traceback frame from a pytest failure."""

    path: str
    lineno: int
    message: str


@dataclass
class LogRecord:
    """Represents a log record matching Python's logging.LogRecord interface.

    Note: Some attribute names use camelCase to maintain compatibility with
    Python's standard logging.LogRecord class.

    The `extra` field captures any additional fields added via Python's
    logging extra parameter (e.g., logger.info("msg", extra={"key": "value"})).
    """

    name: str
    msg: str
    args: Any | None
    levelname: str
    levelno: int
    pathname: str
    filename: str
    module: str
    exc_info: Any | None
    exc_text: str | None
    stack_info: str | None
    lineno: int
    funcName: str  # pylint: disable=invalid-name
    created: float
    msecs: float
    relativeCreated: float  # pylint: disable=invalid-name
    thread: int
    threadName: str  # pylint: disable=invalid-name
    processName: str  # pylint: disable=invalid-name
    process: int
    taskName: str = ""  # pylint: disable=invalid-name
    asctime: str = ""
    message: str = ""  # Formatted message (msg % args), included for completeness
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Log:
    """Container for a list of log records."""

    logs: list[LogRecord]


@dataclass
class StageInfo:
    """Per-stage info (setup/call/teardown) for a single test."""

    duration: float
    outcome: str
    crash: Crash | None = None
    traceback: list[TracebackEntry] | None = None
    stdout: str | None = None
    stderr: str | None = None
    log: Log | None = None
    longrepr: str | None = None


@dataclass
class Test:
    """Single pytest test result with per-stage info."""

    nodeid: str
    lineno: int
    keywords: list[str]
    outcome: str
    setup: StageInfo | None = None
    call: StageInfo | None = None
    teardown: StageInfo | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class CollectorResult:
    """One item discovered by a pytest collector."""

    nodeid: str
    type: str
    lineno: int | None = None
    deselected: bool | None = None


@dataclass
class Collector:
    """A pytest collector and its discovered items."""

    nodeid: str
    outcome: str
    result: list[CollectorResult]
    longrepr: str | None = None


@dataclass
class Summary:
    """Aggregate test counts from a pytest run."""

    collected: int
    total: int
    deselected: int | None = None
    passed: int | None = None
    failed: int | None = None
    xfailed: int | None = None
    xpassed: int | None = None
    error: int | None = None
    skipped: int | None = None


@dataclass
class Warning:  # pylint: disable=redefined-builtin  # pytest-json-report's name
    """A pytest warning emitted during a run."""

    message: str
    code: str | None = None
    path: str | None = None
    nodeid: str | None = None
    when: str | None = None
    category: str | None = None
    filename: str | None = None
    lineno: int | None = None


@dataclass
class ErrorContext:
    """Decoded error context for a non-zero pytest exit."""

    exit_code: int
    exit_code_meaning: str
    error_message: str
    suggestion: str
    traceback: str | None = None


@dataclass
class PytestReport:
    """Top-level pytest-json-report payload parsed into typed fields."""

    created: float
    duration: float
    exitcode: int
    root: str
    environment: dict[str, Any]
    summary: Summary
    collectors: list[Collector] | None = None
    tests: list[Test] | None = None
    warnings: list[Warning] | None = None
    error_context: ErrorContext | None = None


@dataclass
class SanitizedArgs:
    """Result of sanitizing extra_args for pytest execution."""

    cleaned_args: list[str]
    verbosity: int
    notes: list[str]
    has_path_args: bool = False
    show_output: bool = False
    path_args: list[str] = field(default_factory=list)
    collect_only: bool = False
