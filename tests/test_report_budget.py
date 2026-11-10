"""Tests for the shared output budget: `bound_text` and the renderers."""

import pytest

from mcp_tools_py.utils.report_budget import (
    DETAIL_HINT,
    GUARD_CHARS,
    GUARD_HINT,
    GUARD_LINES,
    LINE_CHARS,
    LINES_PER_LOCATION,
    LOCATION_HINT,
    LOCATIONS_PER_RULE,
    SUMMARY_HINT,
    SUMMARY_TOP,
    Location,
    bound_text,
    guard_output,
    render_locations,
    render_summary,
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


def test_one_row_per_file_and_message() -> None:
    """Hits sharing file and message collapse into one row."""
    items = [
        Location("a.py", 3, "msg"),
        Location("a.py", 7, "msg"),
        Location("b.py", 1, "msg"),
    ]
    assert render_locations(items) == ["- a.py: 3, 7 — msg", "- b.py: 1 — msg"]


def test_different_messages_in_same_file_give_two_rows() -> None:
    """Two message texts in one file stay on separate rows."""
    items = [Location("a.py", 1, "first"), Location("a.py", 2, "second")]
    assert render_locations(items) == ["- a.py: 1 — first", "- a.py: 2 — second"]


def test_row_line_numbers_are_capped() -> None:
    """25 hits in one row: 10 numbers, then the hidden count."""
    items = [Location("a.py", i, "msg") for i in range(1, 26)]
    out = render_locations(items)
    shown = ", ".join(str(i) for i in range(1, LINES_PER_LOCATION + 1))
    assert out == [f"- a.py: {shown} (+15) — msg"]


def test_row_without_line_or_message() -> None:
    """A path-only location renders as just the path."""
    assert render_locations([Location("pyproject.toml")]) == ["- pyproject.toml"]


def test_details_follow_the_row_indented() -> None:
    """Details of the row's first item go under the row, indented."""
    items = [Location("a.py", 1, "msg", ("note: one", "note: two"))]
    assert render_locations(items) == [
        "- a.py: 1 — msg",
        "    note: one",
        "    note: two",
    ]


def test_rows_overflow_with_count_and_hint() -> None:
    """15 files: 10 rows, then a count line naming the hint."""
    items = [Location(f"f{i}.py", 1, "msg") for i in range(15)]
    out = render_locations(items)
    assert len(out) == LOCATIONS_PER_RULE + 1
    assert out[-1] == f"... and 5 more locations in 5 more rows — {LOCATION_HINT}"


def test_overflow_counts_hidden_locations_not_rows() -> None:
    """Hidden rows holding several hits count every hit."""
    items = [Location(f"f{i}.py", 1, "msg") for i in range(LOCATIONS_PER_RULE)]
    items += [Location("late.py", n, "msg") for n in range(3)]
    out = render_locations(items, hint="custom")
    assert out[-1] == "... and 3 more locations in 1 more row — custom"


def _rows(n: int) -> list[tuple[str, int, str]]:
    return [(f"R{i:03d}", i + 1, f"(src: {i + 1})") for i in range(n)]


def test_summary_overflow_names_largest_hidden_rules() -> None:
    """30 rows: 20 shown, overflow line names the largest hidden, ends with hint."""
    rows = _rows(30)
    out = render_summary(rows, title="TITLE")
    assert out[0] == "TITLE"
    assert out[1] == "- R000: 1 occurrence (src: 1)"
    assert len([line for line in out if line.startswith("- ")]) == SUMMARY_TOP
    hidden = sum(r[1] for r in rows[SUMMARY_TOP:])
    assert out[-2] == (
        f"... and 10 more rules ({hidden} occurrences), "
        "largest: R029 30, R028 29, R027 28"
    )
    assert out[-1] == SUMMARY_HINT


def test_summary_top_none_lists_all_rows_without_hint() -> None:
    """top=None: every row, no hint lines."""
    out = render_summary(_rows(30), top=None)
    assert len(out) == 30
    assert all(line.startswith("- ") for line in out)


def test_summary_few_rows_end_with_detail_hint() -> None:
    """5 summarised rows: all shown, no 'largest:' line, DETAIL_HINT last."""
    out = render_summary(_rows(5))
    assert len(out) == 6
    assert not any("largest:" in line for line in out)
    assert out[-1] == DETAIL_HINT


def test_summary_empty_rows() -> None:
    """No rows and no title: nothing to render."""
    assert render_summary([]) == []
