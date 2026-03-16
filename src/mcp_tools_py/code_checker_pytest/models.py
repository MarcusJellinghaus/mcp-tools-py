"""
Data models for pytest test results and reports.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Crash:
    path: str
    lineno: int
    message: str


@dataclass
class TracebackEntry:
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
    args: Optional[Any]
    levelname: str
    levelno: int
    pathname: str
    filename: str
    module: str
    exc_info: Optional[Any]
    exc_text: Optional[str]
    stack_info: Optional[str]
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
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Log:
    logs: List[LogRecord]


@dataclass
class StageInfo:
    duration: float
    outcome: str
    crash: Optional[Crash] = None
    traceback: Optional[List[TracebackEntry]] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    log: Optional[Log] = None
    longrepr: Optional[str] = None


@dataclass
class Test:
    nodeid: str
    lineno: int
    keywords: List[str]
    outcome: str
    setup: Optional[StageInfo] = None
    call: Optional[StageInfo] = None
    teardown: Optional[StageInfo] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CollectorResult:
    nodeid: str
    type: str
    lineno: Optional[int] = None
    deselected: Optional[bool] = None


@dataclass
class Collector:
    nodeid: str
    outcome: str
    result: List[CollectorResult]
    longrepr: Optional[str] = None


@dataclass
class Summary:
    collected: int
    total: int
    deselected: Optional[int] = None
    passed: Optional[int] = None
    failed: Optional[int] = None
    xfailed: Optional[int] = None
    xpassed: Optional[int] = None
    error: Optional[int] = None
    skipped: Optional[int] = None


@dataclass
class Warning:
    message: str
    code: Optional[str] = None
    path: Optional[str] = None
    nodeid: Optional[str] = None
    when: Optional[str] = None
    category: Optional[str] = None
    filename: Optional[str] = None
    lineno: Optional[str] = None


@dataclass
class ErrorContext:
    exit_code: int
    exit_code_meaning: str
    error_message: str
    suggestion: str
    traceback: Optional[str] = None
    collection_errors: Optional[List[str]] = None


@dataclass
class PytestReport:
    created: float
    duration: float
    exitcode: int
    root: str
    environment: Dict[str, Any]
    summary: Summary
    collectors: Optional[List[Collector]] = None
    tests: Optional[List[Test]] = None
    warnings: Optional[List[Warning]] = None
    error_context: Optional[ErrorContext] = None
