"""Reporting utilities for mypy results."""

import logging

from mcp_tools_py.code_checker_mypy.models import MypyMessage, MypyResult
from mcp_tools_py.utils.project_config import DEFAULT_CHECK_TIMEOUT
from mcp_tools_py.utils.report_budget import (
    HINT_LINES,
    LOCATIONS_PER_RULE,
    Location,
    render_locations,
    render_summary,
)
from mcp_tools_py.utils.report_counts import format_dir_split, format_total_line, plural

logger = logging.getLogger(__name__)

# Prefix that marks a prompt as a failure rather than a list of type issues
MYPY_FAILURE_PREFIX = "Mypy execution failed:"

MYPY_SUCCESS_TEXT = "Mypy check completed. No type errors found."


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


def format_hint_lines(hint: str | None) -> list[str]:
    """Indent a message's hint for display under its message, capped at HINT_LINES.

    Args:
        hint: The message's hint, newline-separated, or None

    Returns:
        One indented line per kept hint line, then a count of the hidden ones;
        empty when there is no hint.
    """
    if not hint:
        return []
    hint_lines = hint.splitlines()
    out = [f"    {line}" for line in hint_lines[:HINT_LINES]]
    if len(hint_lines) > HINT_LINES:
        hidden = len(hint_lines) - HINT_LINES
        out.append(f"    ... and {plural(hidden, 'more hint line')}")
    return out


def _location(msg: MypyMessage, prefix: str = "") -> Location:
    """Build the `Location` of one mypy message; a negative line is file-level.

    Returns:
        The message's location, with its hint lines as details.
    """
    line = msg.line if msg.line >= 0 else None
    details = tuple(format_hint_lines(msg.hint))
    return Location(msg.file, line, prefix + msg.message, details)


def _group_items(
    messages: list[MypyMessage], last_error: MypyMessage | None
) -> list[Location]:
    """Build a group's locations, moving the last error first if it would be cut.

    Returns:
        The group's locations in display order.
    """
    items = [_location(m) for m in messages]
    if last_error is None or last_error not in messages:
        return items
    target = _location(last_error)
    rows = list(dict.fromkeys((item.path, item.message) for item in items))
    if (target.path, target.message) not in rows[:LOCATIONS_PER_RULE]:
        items.remove(target)
        items.insert(0, target)
    return items


def create_mypy_prompt(result: MypyResult, max_issues: int = 3) -> str | None:
    """Generate LLM-friendly prompt from mypy results.

    Args:
        result: MypyResult from type checking
        max_issues: Number of error codes to show in detail; the rest get one
            summary line each. 0 or less shows counts only.
            When mypy exits with code 2, the code holding the last error is also
            shown in detail without counting against max_issues, including at 0.

    Returns:
        Formatted prompt string or None if no messages
    """
    if not result.messages:
        return None

    max_issues = max(0, max_issues)
    issues = [m for m in result.messages if m.severity != "note"]
    notes = [m for m in result.messages if m.severity == "note"]

    by_code: dict[str, list[MypyMessage]] = {}
    for msg in issues:
        by_code.setdefault(msg.code or "other", []).append(msg)
    groups = sorted(by_code.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    # No field identifies a blocker, so use the last error on rc 2
    errors = [m for m in issues if m.severity == "error"]
    last_error = errors[-1] if result.return_code == 2 and errors else None
    last_code = (last_error.code or "other") if last_error else None
    # The last-error group does not count against the limit
    others = [g for g in groups if g[0] != last_code][:max_issues]
    detailed = [g for g in groups if g[0] == last_code or g in others]
    summarised = [g for g in groups if g not in detailed]

    # Notes join a detailed group of their code; the rest get their own section
    detailed_codes = {code for code, _ in detailed}
    group_notes: dict[str, list[Location]] = {}
    loose_notes: list[Location] = []
    for note in notes if max_issues > 0 else []:
        code = note.code or "misc"
        if code in detailed_codes:
            group_notes.setdefault(code, []).append(_location(note, "note: "))
        else:
            loose_notes.append(_location(note))

    lines: list[str] = []
    for signal in run_signals(result):
        lines += [signal, ""]
    if issues:
        lines += ["Mypy found type issues that need attention:", ""]
    lines += [format_total_line("mypy", len(issues), len(groups)), ""]

    for code, messages in detailed:
        split = format_dir_split(m.file for m in messages)
        lines.append(f"**{code} ({plural(len(messages), 'issue')}) {split}**")
        items = _group_items(messages, last_error) + group_notes.get(code, [])
        lines += [*render_locations(items), ""]

    if loose_notes:
        lines += [f"Notes ({len(loose_notes)}):", *render_locations(loose_notes), ""]

    if summarised:
        rows = [
            (code, len(messages), format_dir_split(m.file for m in messages))
            for code, messages in summarised
        ]
        if max_issues == 0:
            lines += render_summary(rows, top=None)
        else:
            total = sum(count for _, count, _ in rows)
            title = (
                f"--- {plural(len(rows), 'additional rule')} found "
                f"({plural(total, 'occurrence')}) ---"
            )
            lines += render_summary(rows, title=title)
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
    max_issues: int = 3,
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
