"""Shared output budget: limits, truncation and the global guard. See docs/architecture/output-conventions.md."""

from typing import Literal

GUARD_LINES = 400
GUARD_CHARS = 24_000
LINE_CHARS = 500
TOOL_LINES = 300
TOOL_CHARS = 16_000
GUARD_HINT = "Output was cut: narrow the request (fewer targets, a smaller selection) to see the rest."

_FENCE = "```"


def _cap_line(line: str) -> str:
    if len(line) <= LINE_CHARS:
        return line
    return line[:LINE_CHARS] + f" [line truncated: {len(line)} chars]"


def _odd_fences(lines: list[str]) -> bool:
    return sum(1 for line in lines if line.lstrip().startswith(_FENCE)) % 2 == 1


def _fenced(head: list[str], tail: list[str]) -> tuple[list[str], list[str]]:
    """Close a fence left open at the end of head; reopen one in tail."""
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
    """Bound a tool response at the global guard limits."""
    return bound_text(text, GUARD_LINES, GUARD_CHARS, hint=GUARD_HINT)
