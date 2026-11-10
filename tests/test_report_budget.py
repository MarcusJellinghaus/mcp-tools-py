"""Tests for the shared output budget primitive `bound_text`."""

import pytest

from mcp_tools_py.utils.report_budget import (
    GUARD_CHARS,
    GUARD_HINT,
    GUARD_LINES,
    LINE_CHARS,
    bound_text,
    guard_output,
)


def _fence_count(lines: list[str]) -> int:
    return sum(1 for line in lines if line.lstrip().startswith("```"))


def test_short_text_is_unchanged() -> None:
    """Text within budget comes back as it went in."""
    text = "line one\nline two\n"
    assert bound_text(text) == text


def test_long_line_gets_truncation_marker() -> None:
    """A line over LINE_CHARS is cut and names its original length."""
    result = bound_text("x" * 2000)
    assert result == "x" * LINE_CHARS + " [line truncated: 2000 chars]"


def test_many_lines_keep_head_tail_marker_and_hint() -> None:
    """1000 lines: bounded, first and last kept, omitted count right, hint last."""
    lines = [f"line {i}" for i in range(1000)]
    result = bound_text("\n".join(lines), max_lines=50, hint="narrow it")
    out = result.splitlines()
    assert len(out) <= 50
    assert out[0] == "line 0"
    assert out[-2] == "line 999"
    assert out[-1] == "narrow it"
    kept = [line for line in out if line.startswith("line ")]
    omitted = 1000 - len(kept)
    omitted_chars = sum(len(line) for line in lines if line not in kept)
    assert f"[... {omitted} lines / {omitted_chars} chars omitted ...]" in out


def test_char_heavy_text_stays_within_max_chars() -> None:
    """Few long lines over the char budget are cut to max_chars."""
    text = "\n".join("y" * 400 for _ in range(100))
    result = bound_text(text, max_lines=300, max_chars=5000, hint="hint")
    assert len(result) <= 5000
    assert result.endswith("hint")
    assert "omitted ..." in result


def test_keep_tail_keeps_no_head_lines() -> None:
    """keep='tail' starts with the marker, then tail lines."""
    lines = [f"line {i}" for i in range(1000)]
    result = bound_text("\n".join(lines), max_lines=20, keep="tail")
    out = result.splitlines()
    assert out[0].startswith("[... ")
    assert "line 0" not in out
    assert out[-1] == "line 999"


def test_cut_inside_fence_balances_each_part() -> None:
    """A cut inside a fenced block leaves an even number of fences per part."""
    lines = ["```"] + [f"code {i}" for i in range(500)] + ["```"]
    out = bound_text("\n".join(lines), max_lines=30).splitlines()
    marker_idx = next(i for i, line in enumerate(out) if line.startswith("[... "))
    assert _fence_count(out[:marker_idx]) % 2 == 0
    assert _fence_count(out[marker_idx + 1 :]) % 2 == 0


def test_fenced_char_heavy_block_respects_both_limits() -> None:
    """Fences included, the result stays within max_lines and max_chars."""
    lines = ["```"] + ["z" * 300 for _ in range(1000)] + ["```"]
    result = bound_text("\n".join(lines), max_lines=20, max_chars=2000, hint="h")
    assert len(result.splitlines()) <= 20
    assert len(result) <= 2000
    out = result.splitlines()
    marker_idx = next(i for i, line in enumerate(out) if line.startswith("[... "))
    assert _fence_count(out[:marker_idx]) % 2 == 0
    assert _fence_count(out[marker_idx + 1 :]) % 2 == 0


@pytest.mark.parametrize("max_lines", [1, 2, 3, 4])
@pytest.mark.parametrize("hint", [None, "the hint"])
def test_tiny_max_lines_gives_marker_only(max_lines: int, hint: str | None) -> None:
    """No room for head or tail: only the marker (and the hint) remain."""
    text = "\n".join(f"line {i}" for i in range(100))
    out = bound_text(text, max_lines=max_lines, hint=hint).splitlines()
    assert out[0].startswith("[... 100 lines / ")
    assert out[1:] == ([hint] if hint else [])


def test_guard_output_uses_guard_limits() -> None:
    """guard_output bounds at the guard limits and ends with GUARD_HINT."""
    text = "\n".join(f"row {i}" for i in range(5000))
    result = guard_output(text)
    assert len(result.splitlines()) <= GUARD_LINES
    assert len(result) <= GUARD_CHARS
    assert result.endswith(GUARD_HINT)
