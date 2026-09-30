"""Reporting utilities for mypy results."""

import logging

from mcp_tools_py.code_checker_mypy.models import MypyMessage, MypyResult
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.report_counts import format_dir_split, format_total_line, plural

logger = logging.getLogger(__name__)

# Prefix that marks a prompt as a failure rather than a list of type issues
MYPY_FAILURE_PREFIX = "Mypy execution failed:"

MAX_LOCATIONS_PER_CODE = 5


def _format_message(msg: MypyMessage) -> list[str]:
    """Format one message as a location line followed by its indented hint lines."""
    lines = [f"- {msg.file}:{msg.line}:{msg.column} - {msg.message}"]
    if msg.hint:
        lines.extend(f"    {hint_line}" for hint_line in msg.hint.splitlines())
    return lines


def create_mypy_prompt(result: MypyResult, max_issues: int | None = None) -> str | None:
    """Generate LLM-friendly prompt from mypy results.

    Args:
        result: MypyResult from type checking
        max_issues: Number of error codes to show in detail; the rest get one
            summary line each. None shows all; 0 or less shows counts only.

    Returns:
        Formatted prompt string or None if no messages
    """
    if not result.messages:
        return None

    issues = [m for m in result.messages if m.severity != "note"]
    notes = [m for m in result.messages if m.severity == "note"]

    by_code: dict[str, list[MypyMessage]] = {}
    for msg in issues:
        by_code.setdefault(msg.code or "other", []).append(msg)
    groups = sorted(by_code.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    limit = len(groups) if max_issues is None else max(0, max_issues)

    lines: list[str] = []
    if issues:
        lines += ["Mypy found type issues that need attention:", ""]
    lines += [format_total_line("mypy", len(issues), len(groups)), ""]

    for code, messages in groups[:limit]:
        split = format_dir_split(m.file for m in messages)
        lines.append(f"**{code} ({plural(len(messages), 'issue')}) {split}**")
        for msg in messages[:MAX_LOCATIONS_PER_CODE]:
            lines.extend(_format_message(msg))
        if len(messages) > MAX_LOCATIONS_PER_CODE:
            lines.append(f"  ... and {len(messages) - MAX_LOCATIONS_PER_CODE} more")
        lines.append("")

    if groups[limit:]:
        for code, messages in groups[limit:]:
            split = format_dir_split(m.file for m in messages)
            lines.append(f"- {code}: {plural(len(messages), 'occurrence')} {split}")
        lines.append("")

    if notes and (max_issues is None or max_issues > 0):
        lines.append("Notes:")
        for msg in notes:
            lines.extend(_format_message(msg))
        lines.append("")

    if issues:
        lines.append("To fix these issues:")
        lines.append("1. Add missing type annotations where indicated")
        lines.append(
            "2. Ensure all function arguments and return types are properly typed"
        )
        lines.append("3. Fix any import errors or undefined attributes")
        lines.append(
            "4. Review the specific error messages and adjust your code accordingly"
        )

    return "\n".join(lines).rstrip("\n")


def get_mypy_prompt(
    project_dir: str,
    python_executable: str,
    disable_error_codes: list[str] | None = None,
    target_directories: list[str] | None = None,
    follow_imports: str | None = None,
    cache_dir: str | None = None,
    timeout_seconds: int = DEFAULT_CHECK_TIMEOUT,
    max_issues: int | None = None,
) -> str | None:
    """Run mypy and generate an LLM prompt if issues are found.

    This is a convenience function that combines running and reporting.

    Args:
        project_dir: Path to project directory
        python_executable: Python interpreter to use
        disable_error_codes: Error codes to ignore
        target_directories: Directories to check
        follow_imports: How to handle imports ('normal', 'silent', 'skip', 'error');
            omitted from the command line when None
        cache_dir: Custom cache directory for incremental checking
        timeout_seconds: Maximum seconds to wait for mypy
        max_issues: Number of error codes to show in detail (see create_mypy_prompt)

    Returns:
        LLM prompt string or None if no issues
    """
    from mcp_tools_py.code_checker_mypy.runners import run_mypy_check

    result = run_mypy_check(
        project_dir=project_dir,
        python_executable=python_executable,
        disable_error_codes=disable_error_codes,
        target_directories=target_directories,
        follow_imports=follow_imports,
        cache_dir=cache_dir,
        timeout_seconds=timeout_seconds,
    )

    if result.error:
        return f"{MYPY_FAILURE_PREFIX} {result.error}"

    return create_mypy_prompt(result, max_issues=max_issues)
