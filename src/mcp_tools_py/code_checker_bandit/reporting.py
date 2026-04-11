"""
Reporting layer for bandit security analysis results.

Groups findings by test_id, sorts by severity/confidence/frequency,
and formats LLM-optimized output with max_issues detail/summary control.
"""

from collections import defaultdict
from typing import NamedTuple

from mcp_tools_py.code_checker_bandit.models import BanditMessage

MAX_LOCATIONS_PER_ISSUE: int = 50

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
    """Group by test_id, sort by (severity, confidence, -frequency)."""
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


def format_bandit_report(
    messages: list[BanditMessage],
    errors: list[str],
    max_issues: int = 1,
) -> str | None:
    """Format bandit results into LLM-optimized report. Returns None if no issues and no errors."""
    sections: list[str] = []

    if errors:
        error_lines: list[str] = ["File errors (files not scanned):"]
        for error in errors:
            error_lines.append(f"- {error}")
        sections.append("\n".join(error_lines))

    groups = group_and_sort_issues(messages)

    if not groups and not errors:
        return None

    max_issues = max(0, max_issues)

    # Detailed sections for top N issue types
    for group in groups[:max_issues]:
        first = group.messages[0]
        count = len(group.messages)

        lines: list[str] = []
        lines.append(
            f"bandit found {count} issues with {group.test_id} "
            f"({first.test_name}) "
            f"[severity: {first.issue_severity}, confidence: {first.issue_confidence}]"
        )
        lines.append(f"CWE-{first.cwe_id}: {first.cwe_link}")
        lines.append(first.issue_text)
        lines.append("Locations:")

        capped = group.messages[:MAX_LOCATIONS_PER_ISSUE]
        for msg in capped:
            lines.append(f"- {msg.filename}:{msg.line_number}")

        overflow = count - len(capped)
        if overflow > 0:
            lines.append(f"... and {overflow} more occurrences")

        sections.append("\n".join(lines))

    # Summary for remaining issue types
    remaining = groups[max_issues:]
    if remaining:
        summary_lines: list[str] = []
        for group in remaining:
            summary_lines.append(
                f"- {group.test_id} ({group.messages[0].issue_severity}): "
                f"{len(group.messages)} occurrences"
            )
        sections.append("\n".join(summary_lines))

    return "\n\n".join(sections)
