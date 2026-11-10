"""Reporting layer for bandit security analysis results.

Groups findings by test_id, sorts by severity/confidence/frequency,
and formats LLM-optimized output with max_issues detail/summary control.
"""

from collections import defaultdict
from typing import NamedTuple

from mcp_tools_py.code_checker_bandit.models import BanditMessage
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

# Lower number = higher priority
SEVERITY_PRIORITY: dict[str, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
CONFIDENCE_PRIORITY: dict[str, int] = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


class BanditIssueGroup(NamedTuple):
    """A group of bandit messages sharing the same test_id."""

    test_id: str
    messages: list[BanditMessage]


def group_and_sort_issues(
    messages: list[BanditMessage],
) -> list[BanditIssueGroup]:
    """Group by test_id, sort by (severity, confidence, -frequency).

    Returns:
        Issue groups sorted highest severity / confidence / count first.
    """
    groups: dict[str, list[BanditMessage]] = defaultdict(list)
    for msg in messages:
        groups[msg.test_id].append(msg)

    issue_groups = [
        BanditIssueGroup(test_id=test_id, messages=msgs)
        for test_id, msgs in groups.items()
    ]

    issue_groups.sort(
        key=lambda g: (
            SEVERITY_PRIORITY.get(g.messages[0].issue_severity, 99),
            CONFIDENCE_PRIORITY.get(g.messages[0].issue_confidence, 99),
            -len(g.messages),
        )
    )
    return issue_groups


def _summary_rows(groups: list[BanditIssueGroup]) -> list[tuple[str, int, str]]:
    """Build the summary rows for `render_summary`.

    Returns:
        One (rule label, count, directory split) row per group.
    """
    return [
        (
            f"{group.test_id} {group.messages[0].test_name} "
            f"({group.messages[0].issue_severity})",
            len(group.messages),
            format_dir_split(msg.filename for msg in group.messages),
        )
        for group in groups
    ]


def format_bandit_report(
    messages: list[BanditMessage],
    errors: list[str],
    max_issues: int = 1,
) -> str | None:
    """Format bandit results into an LLM-optimized report.

    Returns:
        Formatted report string, or None if there are no issues and no errors.
    """
    groups = group_and_sort_issues(messages)

    if not groups and not errors:
        return None

    sections: list[str] = [format_total_line("bandit", len(messages), len(groups))]

    if errors:
        error_lines: list[str] = ["File errors (files not scanned):"]
        for error in errors:
            error_lines.append(f"- {error}")
        sections.append("\n".join(error_lines))

    max_issues = max(0, max_issues)

    if max_issues == 0:
        if groups:
            sections.append("\n".join(render_summary(_summary_rows(groups), top=None)))
        return "\n\n".join(sections)

    # Detailed sections for top N issue types
    for group in groups[:max_issues]:
        first = group.messages[0]
        count = len(group.messages)
        split = format_dir_split(msg.filename for msg in group.messages)

        lines: list[str] = []
        lines.append(
            f"bandit found {plural(count, 'issue')} with {group.test_id} "
            f"{first.test_name} {split} "
            f"[severity: {first.issue_severity}, confidence: {first.issue_confidence}]"
        )
        if first.cwe_id:
            lines.append(f"CWE-{first.cwe_id}: {first.cwe_link}")
        lines.append(first.issue_text)
        lines.append("Locations:")
        lines.extend(
            render_locations(
                [Location(msg.filename, msg.line_number) for msg in group.messages]
            )
        )
        sections.append("\n".join(lines))

    # Summary for remaining issue types
    remaining = groups[max_issues:]
    if remaining:
        remaining_count = sum(len(g.messages) for g in remaining)
        title = (
            f"--- {plural(len(remaining), 'additional rule')} found "
            f"({remaining_count} occurrences) ---"
        )
        summary = render_summary(_summary_rows(remaining), title=title)
        sections.append("\n".join(summary))

    return "\n\n".join(sections)
