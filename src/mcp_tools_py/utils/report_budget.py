"""Shared output budget: limits, truncation and the global guard. See docs/architecture/output-conventions.md."""

import heapq
from typing import Literal, NamedTuple, Sequence

from mcp_tools_py.utils.report_counts import plural

GUARD_LINES = 400
GUARD_CHARS = 24_000
LINE_CHARS = 500
TOOL_LINES = 300
TOOL_CHARS = 16_000
LOCATIONS_PER_RULE = 10
LINES_PER_LOCATION = 10
SUMMARY_TOP = 20
MAX_FAILURES = 10
FAILED_IDS = 50
MAX_COLLECTOR_IDS = 10
ERROR_TAIL_LINES = 50
HINT_LINES = 5
GUARD_HINT = "Output was cut: narrow the request (fewer targets, a smaller selection) to see the rest."
SUMMARY_HINT = "Use max_issues=0 to list all rules."
DETAIL_HINT = "Use max_issues=N to see locations for the top N rules."
LOCATION_HINT = "narrow target_directories or fix these and rerun"

_FENCE = "```"


def _cap_line(line: str) -> str:
    if len(line) <= LINE_CHARS:
        return line
    return line[:LINE_CHARS] + f" [line truncated: {len(line)} chars]"


def _odd_fences(lines: list[str]) -> bool:
    return sum(1 for line in lines if line.lstrip().startswith(_FENCE)) % 2 == 1


def _fenced(head: list[str], tail: list[str]) -> tuple[list[str], list[str]]:
    """Close a fence left open at the end of head; reopen one in tail.

    Returns:
        The head and tail with their fences balanced.
    """
    out_head = head + [_FENCE] if _odd_fences(head) else head
    out_tail = [_FENCE] + tail if _odd_fences(tail) else tail
    return out_head, out_tail


def bound_text(
    text: str,
    max_lines: int = TOOL_LINES,
    max_chars: int = TOOL_CHARS,
    hint: str | None = None,
    keep: Literal["both", "tail"] = "both",
) -> str:
    """Bound `text` to `max_lines` lines and `max_chars` chars.

    Each line is capped at LINE_CHARS. Over budget, the head and tail are kept
    (only the tail with keep="tail"), the middle becomes a counted marker, a
    code fence left open at the cut is balanced, and `hint` ends the text.

    Returns:
        The bounded text; `text` itself when already within budget.
    """
    original = text.splitlines()
    lines = [_cap_line(line) for line in original]
    joined = "\n".join(lines)
    if len(lines) <= max_lines and len(joined) <= max_chars:
        return text if lines == original else joined

    def marker(head_n: int, tail_n: int) -> str:
        omitted = original[head_n : len(original) - tail_n]
        omitted_chars = sum(len(line) for line in omitted)
        return f"[... {len(omitted)} lines / {omitted_chars} chars omitted ...]"

    hint_lines = [hint] if hint else []
    room = max_lines - 2 - 2
    if room < 1:
        return "\n".join([marker(0, 0)] + hint_lines)[:max_chars]

    room = min(room, len(lines))
    head_n = 0 if keep == "tail" else room * 2 // 3
    tail_n = room - head_n
    head, tail = lines[:head_n], lines[len(lines) - tail_n :]

    def render() -> str:
        out_head, out_tail = _fenced(head, tail)
        mid = [marker(len(head), len(tail))]
        return "\n".join(out_head + mid + out_tail + hint_lines)

    result = render()
    while len(result) > max_chars and (head or tail):
        if len(head) > len(tail):
            head.pop()
        else:
            tail.pop(0)
        result = render()
    return result[:max_chars]


def guard_output(text: str) -> str:
    """Bound a tool response at the global guard limits.

    Returns:
        The bounded text, ending with GUARD_HINT when cut.
    """
    return bound_text(text, GUARD_LINES, GUARD_CHARS, hint=GUARD_HINT)


class Location(NamedTuple):
    """One finding location; `details` are extra lines shown under its row."""

    path: str
    line: int | None = None
    message: str | None = None
    details: tuple[str, ...] = ()


def _location_row(group: list[Location]) -> list[str]:
    first = group[0]
    nums = [str(item.line) for item in group if item.line is not None]
    text = f"- {first.path}"
    if nums:
        text += ": " + ", ".join(nums[:LINES_PER_LOCATION])
        if len(nums) > LINES_PER_LOCATION:
            text += f" (+{len(nums) - LINES_PER_LOCATION})"
    if first.message:
        text += f" — {first.message}"
    return [text] + [f"    {detail}" for detail in first.details]


def render_locations(items: Sequence[Location], hint: str = LOCATION_HINT) -> list[str]:
    """Render locations as rows grouped by (path, message), capped per rule.

    Returns:
        At most LOCATIONS_PER_RULE rows, then a count line naming `hint` when
        rows were hidden.
    """
    rows: dict[tuple[str, str | None], list[Location]] = {}
    for item in items:
        rows.setdefault((item.path, item.message), []).append(item)
    groups = list(rows.values())
    out: list[str] = []
    for group in groups[:LOCATIONS_PER_RULE]:
        out.extend(_location_row(group))
    rest = groups[LOCATIONS_PER_RULE:]
    if rest:
        hidden = sum(len(group) for group in rest)
        out.append(
            f"... and {plural(hidden, 'more location')} in "
            f"{plural(len(rest), 'more row')} — {hint}"
        )
    return out


def render_summary(
    rows: Sequence[tuple[str, int, str]],
    title: str | None = None,
    top: int | None = SUMMARY_TOP,
    hint: str = SUMMARY_HINT,
    detail_hint: str | None = DETAIL_HINT,
) -> list[str]:
    """Render (label, count, dir split) rule rows, capped at `top`.

    `top=None` lists every row and adds no hint. Otherwise the output ends
    with `hint` when rows overflow `top`, else with `detail_hint`.

    Returns:
        The summary lines.
    """
    out = [title] if title else []
    shown = rows if top is None else rows[:top]
    out.extend(
        f"- {label}: {plural(count, 'occurrence')} {split}"
        for label, count, split in shown
    )
    if rows and top is not None and detail_hint:
        out.append(detail_hint)
    rest = rows[len(shown) :]
    if rest:
        largest = heapq.nlargest(3, rest, key=lambda row: row[1])
        named = ", ".join(f"{label} {count}" for label, count, _ in largest)
        total = sum(count for _, count, _ in rest)
        out += [
            f"... and {len(rest)} more rules ({total} occurrences), largest: {named}",
            hint,
        ]
    return out
