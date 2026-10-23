"""Reporting layer for deptry results.

Groups findings by code, sorts by frequency, and formats LLM-optimized
output with max_issues detail/summary control.
"""

from collections import defaultdict

from mcp_tools_py.code_checker_deptry.runners import DeptryMessage
from mcp_tools_py.utils.report_counts import (
    format_dir_split,
    format_total_line,
    plural,
)

MAX_LOCATIONS_PER_ISSUE: int = 50


def _location(msg: DeptryMessage) -> str:
    """Format one finding as a location line.

    Returns:
        ``- <file>: '<module>'`` when the finding has no line (e.g. DEP002 in
        ``pyproject.toml``), else ``- <file>:<line>:<column> <module> <message>``.
    """
    if msg.line is None:
        return f"- {msg.file}: '{msg.module}'"
    return f"- {msg.file}:{msg.line}:{msg.column} {msg.module} {msg.message}"


def format_deptry_report(
    messages: list[DeptryMessage],
    max_issues: int = 1,
) -> str | None:
    """Format deptry results into an LLM prompt.

    Returns:
        Formatted report string, or None if there are no issues.
    """
    if not messages:
        return None

    by_code: dict[str, list[DeptryMessage]] = defaultdict(list)
    for msg in messages:
        by_code[msg.code].append(msg)
    groups = sorted(by_code.items(), key=lambda item: (-len(item[1]), item[0]))

    max_issues = max(0, max_issues)
    sections: list[str] = [format_total_line("deptry", len(messages), len(groups))]

    # Detailed sections for top N codes
    for code, msgs in groups[:max_issues]:
        count = len(msgs)
        split = format_dir_split(m.file for m in msgs)

        lines: list[str] = [
            f"deptry found {plural(count, 'issue')} with rule {code} {split}.",
            "Locations:",
        ]
        capped = msgs[:MAX_LOCATIONS_PER_ISSUE]
        lines.extend(_location(msg) for msg in capped)

        overflow = count - len(capped)
        if overflow > 0:
            lines.append(f"... and {overflow} more occurrences")

        sections.append("\n".join(lines))

    # Summary for remaining codes
    remaining = groups[max_issues:]
    if remaining:
        sections.append(
            "\n".join(
                f"- {code}: {plural(len(msgs), 'occurrence')} "
                f"{format_dir_split(m.file for m in msgs)}"
                for code, msgs in remaining
            )
        )

    return "\n\n".join(sections)
