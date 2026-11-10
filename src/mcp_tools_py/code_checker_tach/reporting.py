"""Reporting layer for tach architecture-boundary results.

Groups diagnostics by severity, kind and module pair, errors first, and
formats LLM-optimized output with max_issues detail/summary control.
"""

from collections import defaultdict

from mcp_tools_py.code_checker_tach.parsers import TachDiagnostic
from mcp_tools_py.code_checker_tach.runners import TachResult
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

TACH_HINT = "fix these and rerun"
_GLOBAL = "(global)"


def _label(diagnostic: TachDiagnostic) -> str:
    if diagnostic.usage_module and diagnostic.dependency:
        return (
            f"{diagnostic.kind}: {diagnostic.usage_module} -> {diagnostic.dependency}"
        )
    return diagnostic.kind


def _group(diagnostics: list[TachDiagnostic]) -> list[list[TachDiagnostic]]:
    """Group by (severity, kind, module pair), errors first, then largest.

    Returns:
        The diagnostic groups in report order.
    """
    groups: dict[tuple[str, str], list[TachDiagnostic]] = defaultdict(list)
    for diagnostic in diagnostics:
        groups[(diagnostic.severity, _label(diagnostic))].append(diagnostic)
    return sorted(
        groups.values(),
        key=lambda group: (group[0].severity != "error", -len(group)),
    )


def _files(group: list[TachDiagnostic]) -> list[str]:
    return [d.file or _GLOBAL for d in group]


def _summary_rows(groups: list[list[TachDiagnostic]]) -> list[tuple[str, int, str]]:
    return [
        (
            f"[{group[0].severity}] {_label(group[0])}",
            len(group),
            format_dir_split(_files(group)),
        )
        for group in groups
    ]


def _status_line(result: TachResult) -> str:
    return "tach check passed" if result.return_code == 0 else "tach check failed"


def format_tach_report(result: TachResult, max_issues: int = 1) -> str:
    """Format a tach result into an LLM-optimized report.

    Returns:
        The error text; the status line and the unparsed output as-is; a
        no-output line; or the status line and the grouped report.
    """
    if result.error is not None:
        return result.error
    if result.raw is not None:
        return f"{_status_line(result)}:\n{result.raw}"
    if not result.diagnostics:
        if result.return_code == 0:
            return "tach check passed (no output)."
        return f"tach check failed (exit code {result.return_code}, no output)."

    errors = [d for d in result.diagnostics if d.severity == "error"]
    warnings = len(result.diagnostics) - len(errors)
    groups = _group(result.diagnostics)

    if errors:
        error_groups = sum(1 for group in groups if group[0].severity == "error")
        total = format_total_line("tach", len(errors), error_groups)
        if warnings:
            total += f", plus {plural(warnings, 'warning')}"
        sections = [f"{_status_line(result)}\n{total}"]
    elif result.return_code == 0:
        sections = [f"tach check passed with {plural(warnings, 'warning')}"]
    else:
        sections = [f"tach check failed with {plural(warnings, 'warning')}"]

    max_issues = max(0, max_issues)
    if max_issues == 0:
        sections.append("\n".join(render_summary(_summary_rows(groups), top=None)))
        return "\n\n".join(sections)

    for group in groups[:max_issues]:
        lines = [
            f"tach found {plural(len(group), group[0].severity)} with "
            f"{_label(group[0])} {format_dir_split(_files(group))}",
            "Locations:",
        ]
        lines.extend(
            render_locations(
                [Location(d.file or _GLOBAL, d.line, d.message) for d in group],
                TACH_HINT,
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
        sections.append("\n".join(render_summary(_summary_rows(remaining), title)))
    return "\n\n".join(sections)
