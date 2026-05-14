"""Reporting layer for ruff analysis results.

Groups violations by rule code, sorts by prefix category then frequency,
and formats LLM-optimized output with max_issues detail/summary control.
"""

from collections import defaultdict
from typing import List, NamedTuple, Optional

from mcp_tools_py.code_checker_ruff.models import RuffMessage

MAX_LOCATIONS_PER_ISSUE: int = 50

# Lower number = higher priority
RULE_PREFIX_PRIORITY: dict[str, int] = {
    "E": 0,  # errors
    "W": 1,  # warnings
    "F": 2,  # pyflakes
    "D": 3,  # pydocstyle
    "DOC": 4,  # pydoclint
}


class RuffIssueGroup(NamedTuple):
    """A group of ruff messages sharing the same rule code."""

    code: str
    messages: List[RuffMessage]


def get_rule_prefix(code: str) -> str:
    """Extract prefix from rule code: 'D100' -> 'D', 'DOC201' -> 'DOC'.

    Returns:
        Leading alphabetic prefix of `code`.
    """
    prefix = ""
    for char in code:
        if char.isalpha():
            prefix += char
        else:
            break
    return prefix


def group_and_sort_issues(
    messages: List[RuffMessage],
) -> List[RuffIssueGroup]:
    """Group by code, sort by prefix priority then frequency (descending).

    Returns:
        Issue groups sorted by rule-prefix priority and frequency.
    """
    groups: dict[str, list[RuffMessage]] = defaultdict(list)
    for msg in messages:
        groups[msg.code].append(msg)

    issue_groups = [
        RuffIssueGroup(code=code, messages=msgs) for code, msgs in groups.items()
    ]

    issue_groups.sort(
        key=lambda g: (
            RULE_PREFIX_PRIORITY.get(get_rule_prefix(g.code), 99),
            -len(g.messages),
        )
    )
    return issue_groups


def format_ruff_check_report(
    messages: List[RuffMessage],
    max_issues: int = 1,
) -> Optional[str]:
    """Format ruff check results into an LLM prompt.

    Returns:
        Formatted report string, or None if there are no issues.
    """
    groups = group_and_sort_issues(messages)
    if not groups:
        return None

    max_issues = max(0, max_issues)
    sections: list[str] = []

    # Detailed sections for top N issue types
    for group in groups[:max_issues]:
        url = group.messages[0].url
        message_text = group.messages[0].message
        count = len(group.messages)

        lines: list[str] = []
        url_part = f" ({url})" if url else ""
        lines.append(f"ruff found {count} issues with rule {group.code}{url_part}.")
        lines.append(message_text)
        lines.append("Locations:")

        capped = group.messages[:MAX_LOCATIONS_PER_ISSUE]
        for msg in capped:
            lines.append(f"- {msg.filename}:{msg.line}:{msg.column}")

        overflow = count - len(capped)
        if overflow > 0:
            lines.append(f"... and {overflow} more occurrences")

        sections.append("\n".join(lines))

    # Summary for remaining issue types
    remaining = groups[max_issues:]
    if remaining:
        summary_lines: list[str] = []
        for group in remaining:
            summary_lines.append(f"- {group.code}: {len(group.messages)} occurrences")
        sections.append("\n".join(summary_lines))

    return "\n\n".join(sections)


def format_ruff_fix_report(
    changed_files: List[str],
    remaining_messages: List[RuffMessage],
) -> str:
    """Format ruff fix results: changed files + remaining error summary.

    Returns:
        Multi-line report listing fixes and any unfixed issues.
    """
    lines: list[str] = [f"Ruff applied fixes to {len(changed_files)} files:"]
    for filepath in changed_files:
        lines.append(f"- {filepath}")

    if remaining_messages:
        groups = group_and_sort_issues(remaining_messages)
        total_count = len(remaining_messages)
        rule_count = len(groups)
        lines.append("")
        lines.append(
            f"{total_count} remaining issues ({rule_count} rule types) "
            f"not auto-fixable:"
        )
        for group in groups:
            lines.append(f"- {group.code}: {len(group.messages)} occurrences")

    return "\n".join(lines)
