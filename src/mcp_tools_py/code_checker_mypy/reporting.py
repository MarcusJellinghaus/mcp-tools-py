"""Reporting utilities for mypy results."""

import logging

from mcp_tools_py.code_checker_mypy.models import MypyMessage, MypyResult
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.report_counts import format_dir_split, format_total_line, plural

logger = logging.getLogger(__name__)

# Prefix that marks a prompt as a failure rather than a list of type issues
MYPY_FAILURE_PREFIX = "Mypy execution failed:"

MYPY_SUCCESS_TEXT = "Mypy check completed. No type errors found."

MAX_LOCATIONS_PER_CODE = 5


def run_signals(result: MypyResult) -> list[str]:
    """Collect what a report must say about the run itself.

    Args:
        result: MypyResult from type checking

    Returns:
        The early-stop line and the stderr warning, each only when it applies.
    """
    signals = []
    if result.return_code == 2 and result.messages:
        signals.append(
            "mypy exited with code 2, more errors may appear after these are fixed"
        )
    if result.stderr:
        signals.append(f"Warning from mypy: {result.stderr}")
    return signals


def _format_message(msg: MypyMessage) -> list[str]:
    """Format one mypy message.

    Returns:
        The location line followed by the message's indented hint lines.
    """
    location = msg.file if msg.line < 0 else f"{msg.file}:{msg.line}:{msg.column}"
    lines = [f"- {location} - {msg.message}"]
    if msg.hint:
        lines.extend(f"    {hint_line}" for hint_line in msg.hint.splitlines())
    return lines


def create_mypy_prompt(result: MypyResult, max_issues: int | None = None) -> str | None:
    """Generate LLM-friendly prompt from mypy results.

    Args:
        result: MypyResult from type checking
        max_issues: Number of error codes to show in detail; the rest get one
            summary line each. None shows all; 0 or less shows counts only.
            When mypy exits with code 2, the code holding the last error is also
            shown in detail without counting against max_issues, including at 0.

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

    # No field identifies a blocker, so use the last error on rc 2
    errors = [m for m in issues if m.severity == "error"]
    last_error = errors[-1] if result.return_code == 2 and errors else None
    last_code = (last_error.code or "other") if last_error else None
    # The last-error group does not count against the limit
    others = [g for g in groups if g[0] != last_code][:limit]
    detailed = [g for g in groups if g[0] == last_code or g in others]
    summarised = [g for g in groups if g not in detailed]

    lines: list[str] = []
    for signal in run_signals(result):
        lines += [signal, ""]
    if issues:
        lines += ["Mypy found type issues that need attention:", ""]
    lines += [format_total_line("mypy", len(issues), len(groups)), ""]

    for code, messages in detailed:
        split = format_dir_split(m.file for m in messages)
        lines.append(f"**{code} ({plural(len(messages), 'issue')}) {split}**")
        shown = messages[:MAX_LOCATIONS_PER_CODE]
        if last_error in messages and last_error not in shown:
            shown.append(last_error)
        for msg in shown:
            lines.extend(_format_message(msg))
        if len(messages) > len(shown):
            lines.append(f"  ... and {len(messages) - len(shown)} more")
        lines.append("")

    if summarised:
        for code, messages in summarised:
            split = format_dir_split(m.file for m in messages)
            lines.append(f"- {code}: {plural(len(messages), 'occurrence')} {split}")
        lines.append("")

    if notes and (max_issues is None or max_issues > 0):
        lines.append("Notes:")
        for msg in notes:
            lines.extend(_format_message(msg))
        lines.append("")

    if issues and result.return_code != 2:
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
        LLM prompt string; the success text plus the warning for a passing run
        with stderr; None only for a passing run without stderr
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

    prompt = create_mypy_prompt(result, max_issues=max_issues)
    if prompt is None and result.stderr:
        return "\n\n".join([MYPY_SUCCESS_TEXT, *run_signals(result)])
    return prompt
