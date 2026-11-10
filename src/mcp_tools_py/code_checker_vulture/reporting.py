"""Reporting layer for vulture dead-code results.

Groups messages by kind, sorts by confidence/frequency, and formats
LLM-optimized output with max_issues detail/summary control.
"""

from collections import defaultdict

from mcp_tools_py.code_checker_vulture.parsers import VultureMessage
from mcp_tools_py.code_checker_vulture.runners import VultureResult
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

VULTURE_HINT = "narrow target_directories, raise min_confidence, or fix these and rerun"
VULTURE_NO_ISSUES = "vulture found no issues."


def _group_by_kind(messages: list[VultureMessage]) -> list[list[VultureMessage]]:
    """Group by kind, highest confidence first, then most frequent.

    Returns:
        The message groups in report order.
    """
    groups: dict[str, list[VultureMessage]] = defaultdict(list)
    for message in messages:
        groups[message.kind].append(message)
    return sorted(
        groups.values(),
        key=lambda group: (-max(m.confidence for m in group), -len(group)),
    )


def _summary_rows(groups: list[list[VultureMessage]]) -> list[tuple[str, int, str]]:
    return [
        (group[0].kind, len(group), format_dir_split(m.file for m in group))
        for group in groups
    ]


def format_vulture_report(result: VultureResult, max_issues: int = 1) -> str:
    """Format a vulture result into an LLM-optimized report.

    Returns:
        The error text; the unparsed output as-is when nothing parsed (e.g.
        --make-whitelist); a no-issues line; or the grouped report.
    """
    if result.error is not None:
        return result.error
    if not result.messages:
        return "\n".join(result.unparsed) if result.unparsed else VULTURE_NO_ISSUES

    groups = _group_by_kind(result.messages)
    sections = [format_total_line("vulture", len(result.messages), len(groups))]
    max_issues = max(0, max_issues)

    if max_issues == 0:
        sections.append("\n".join(render_summary(_summary_rows(groups), top=None)))
    else:
        for group in groups[:max_issues]:
            split = format_dir_split(m.file for m in group)
            confidence = max(m.confidence for m in group)
            lines = [
                f"vulture found {plural(len(group), 'issue')} with {group[0].kind} "
                f"{split} [max confidence: {confidence}%]",
                "Locations:",
            ]
            lines.extend(
                render_locations(
                    [Location(m.file, m.line, m.message) for m in group],
                    VULTURE_HINT,
                )
            )
            sections.append("\n".join(lines))

        remaining = groups[max_issues:]
        if remaining:
            count = sum(len(group) for group in remaining)
            title = (
                f"--- {plural(len(remaining), 'additional rule')} found "
                f"({count} occurrences) ---"
            )
            summary = render_summary(_summary_rows(remaining), title=title)
            sections.append("\n".join(summary))

    if result.unparsed:
        sections.append("\n".join(["Unparsed vulture output:", *result.unparsed]))
    return "\n\n".join(sections)
