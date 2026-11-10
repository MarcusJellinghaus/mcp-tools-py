"""Reporting layer for ruff analysis results.

Groups violations by rule code, sorts by prefix category then frequency,
and formats LLM-optimized output with max_issues detail/summary control.
"""

from collections import defaultdict
from typing import List, NamedTuple, Optional

from mcp_tools_py.utils.report_budget import (
    SUMMARY_TOP,
    Location,
    render_locations,
    render_summary,
)
from mcp_tools_py.utils.report_counts import (
    format_dir_split,
    format_total_line,
    plural,
)
from mcp_tools_py.utils.ruff_parsing import RuffMessage

# Lower number = higher priority
RULE_PREFIX_PRIORITY: dict[str, int] = {
    "E": 0,  # errors
    "W": 1,  # warnings
    "F": 2,  # pyflakes
    "D": 3,  # pydocstyle
    "DOC": 4,  # pydoclint
}

FIX_HINT = "Use run_ruff_check(max_issues=0) to list all remaining rules."
FILES_HINT = "narrow target_directories to list fewer changed files"


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


def _rule_label(code: str, url: str | None) -> str:
    """Build ``"<code> <name>"`` from the rule URL's last segment.

    Returns:
        Code and rule name, or the code alone when ``url`` is empty or None.
    """
    name = url.rstrip("/").rsplit("/", 1)[-1] if url else ""
    return f"{code} {name}".strip()


def _summary_rows(groups: List[RuffIssueGroup]) -> list[tuple[str, int, str]]:
    """Build the summary rows for `render_summary`.

    Returns:
        One (rule label, count, directory split) row per group.
    """
    return [
        (
            _rule_label(group.code, group.messages[0].url),
            len(group.messages),
            format_dir_split(m.filename for m in group.messages),
        )
        for group in groups
    ]


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
    sections: list[str] = [format_total_line("ruff", len(messages), len(groups))]

    if max_issues == 0:
        sections.append("\n".join(render_summary(_summary_rows(groups), top=None)))
        return "\n\n".join(sections)

    # Detailed sections for top N issue types
    for group in groups[:max_issues]:
        label = _rule_label(group.code, group.messages[0].url)
        count = len(group.messages)
        split = format_dir_split(m.filename for m in group.messages)
        rows = render_locations(
            [Location(m.filename, m.line, m.message) for m in group.messages]
        )
        lines = [
            f"ruff found {plural(count, 'issue')} with rule {label} {split}.",
            "Locations:",
            *rows,
        ]
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


def format_ruff_fix_report(
    changed_files: List[str],
    remaining_messages: List[RuffMessage],
) -> str:
    """Format ruff fix results: changed files + remaining error summary.

    Returns:
        Multi-line report listing fixes and any unfixed issues.
    """
    count = len(changed_files)
    header = f"Ruff applied fixes to {plural(count, 'file')}"
    if changed_files:
        header += f" {format_dir_split(changed_files)}"
    lines: list[str] = [header + ":"]
    lines.extend(f"- {filepath}" for filepath in changed_files[:SUMMARY_TOP])
    hidden = count - SUMMARY_TOP
    if hidden > 0:
        lines.append(f"... and {hidden} more files — {FILES_HINT}")

    if remaining_messages:
        groups = group_and_sort_issues(remaining_messages)
        title = (
            f"{len(remaining_messages)} remaining issues ({len(groups)} rule types) "
            f"not auto-fixable:"
        )
        lines.append("")
        lines.extend(
            render_summary(
                _summary_rows(groups),
                title=title,
                hint=FIX_HINT,
                detail_hint="Use run_ruff_check to see their locations.",
            )
        )

    return "\n".join(lines)
