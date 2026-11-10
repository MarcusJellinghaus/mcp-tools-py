"""Reporting layer for deptry results.

Groups findings by code, sorts by frequency, and formats LLM-optimized
output with max_issues detail/summary control.
"""

from collections import defaultdict

from mcp_tools_py.code_checker_deptry.runners import DeptryMessage
from mcp_tools_py.utils.report_budget import (
    Location,
    render_locations,
    render_summary,
)
from mcp_tools_py.utils.report_counts import (
    format_dir_split,
    format_total_line,
    plural,
)


def _location(msg: DeptryMessage) -> Location:
    """Build the location for one finding.

    Returns:
        A location carrying ``'<module>'`` when the finding has no line (e.g.
        DEP002 in ``pyproject.toml``), else the line and ``<module> <message>``.
    """
    if msg.line is None:
        return Location(msg.file, None, f"'{msg.module}'")
    return Location(msg.file, msg.line, f"{msg.module} {msg.message}")


def _summary_rows(
    groups: list[tuple[str, list[DeptryMessage]]],
) -> list[tuple[str, int, str]]:
    """Build the summary rows for `render_summary`.

    Returns:
        One (code, count, directory split) row per group.
    """
    return [
        (code, len(msgs), format_dir_split(m.file for m in msgs))
        for code, msgs in groups
    ]


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

    if max_issues == 0:
        sections.append("\n".join(render_summary(_summary_rows(groups), top=None)))
        return "\n\n".join(sections)

    # Detailed sections for top N codes
    for code, msgs in groups[:max_issues]:
        count = len(msgs)
        split = format_dir_split(m.file for m in msgs)
        lines: list[str] = [
            f"deptry found {plural(count, 'issue')} with rule {code} {split}.",
            "Locations:",
            *render_locations([_location(msg) for msg in msgs]),
        ]
        sections.append("\n".join(lines))

    # Summary for remaining codes
    remaining = groups[max_issues:]
    if remaining:
        remaining_count = sum(len(msgs) for _, msgs in remaining)
        title = (
            f"--- {plural(len(remaining), 'additional rule')} found "
            f"({remaining_count} occurrences) ---"
        )
        summary = render_summary(_summary_rows(remaining), title=title)
        sections.append("\n".join(summary))

    return "\n\n".join(sections)
