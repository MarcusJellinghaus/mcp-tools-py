# Step 7 — `report_extras.py`: flags, sections, empty-result lines

## LLM prompt
Read `pr_info/steps/summary.md` (design changes 4 and 5) and this file; issue #293 D7, D17, D21, the flag table
and "Empty results" define the behaviour. Implement test-first. Run pylint, mypy and the non-integration pytest
suite. One commit.

## WHERE
- Create `src/mcp_tools_py/code_checker_pytest/report_extras.py`
- Tests: new `tests/test_code_checker_pytest/test_report_extras.py`

## WHAT
```python
DEFAULT_DURATIONS_MIN = 0.005

@dataclass(frozen=True)
class ReportFlags:
    letters: frozenset[str]      # supported section letters {"s","w"} in the effective -r, after resolution
    r_label: str | None          # call spelling of -r when it comes from extra_args, else None
    no_effect: str               # unsupported/unknown letters for the note (call only), "" when none
    durations: int | None        # effective --durations, None when not in effect
    durations_min: float         # effective --durations-min, else DEFAULT_DURATIONS_MIN
    durations_min_in_call: bool
    show_capture: str | None     # effective --show-capture value
    snapshot_update: bool
    disable_warnings: bool

def resolve_report_chars(value: str) -> tuple[frozenset[str], str]:
    """pytest's getreportopt with this tool's deviations → (section letters, no-effect letters)."""

def report_flags(effective: EffectiveConfig) -> ReportFlags: ...

def report_sections(report: PytestReport, flags: ReportFlags, max_lines: int, max_chars: int) -> str:
    """-rs, -rw, --durations sections and the empty-result line, within the budget."""
```

## ALGORITHM
```
resolve_report_chars(value):
    opts = ""; for ch in value (F/S lowered): a → "sxXEfw"; A → "PpsxXEfw"; N → ""; else add ch if new
    tail = value after the last a/A/N; no_effect = ordered unique chars of tail not in "sSwfFEaAN" and not space
    return frozenset(opts) & {"s","w"}, no_effect
report_sections: out = Sections(max_lines, max_chars); sections = flags.letters - ({"w"} if disable_warnings)
    present = [(label, header, rows) for each of:
               ("skip reasons (-rs)", "Skip reasons:", skip_lines) if "s" in sections and folded,
               ("warnings (-rw)", "Warnings:", warning lines) if "w" in sections and groups,
               ("durations", durations header, rows >= min of the cut, + hidden line) if durations is not None]
               # durations cut = all if 0 else first N
    for index, (label, header, rows) in enumerate(present):   # even share of what is left, like _render_tests
        share = len(present) - index
        text = _head_rows(header, rows, out.lines // share, out.chars // share)
        if not (text and out.add(text)): out.dropped.append(label)
_head_rows(header, rows, max_lines, max_chars) -> str:      # head-only cut: rows are slowest / most frequent first
    keep the header and the first rows that fit, leaving one line for the omitted-count line;
    if rows were left out: append f"({omitted} more rows not shown, budget used up.)"
    "" when not even the header, one row and that line fit
    if r_label: empties = ["no skipped tests" if s & none, "no warnings" if w & none]; if empties: out.add(f"{r_label}: {', '.join(empties)}.")
    return out.text()
```
Duration row: `f"{d.seconds:.2f}s {d.when} {d.nodeid}"`; hidden line:
`f"({hidden} durations < {flags.durations_min:g}s hidden; pass --durations-min=0 to show them.)"`.
`--durations` value not an int → treat as not in effect.
Report sections are cut, not dropped whole: a long `--durations=0`, `-rs` or `-rw` list still shows its first rows.
`bound_text` is not used because it keeps head and tail; these lists are sorted, so only the head matters. A
section is named in the `Not shown, budget used up:` notice only when not even its first row fits.

## DATA
- `resolve_report_chars("a") == ({"s","w"}, "")`; `"ax"` → note `x`; `"xa"`, `"xN"` → no note; `"z"` → `z`;
  `"S"` → `{"s"}`; `"N"` → empty; `"fE"` → empty, no note; `"sxp"` → `{"s"}`, note `xp`.
- Config-sourced `-ra` on a clean report → `""` (nothing to show, no empty line).
- Call `-ra` clean → `"-ra: no skipped tests, no warnings."`; with `--disable-warnings` → `"-ra: no skipped tests."`.
- `-svrw` (sanitized to `-rw`) → label `-rw`.

## Tests (write first)
All `resolve_report_chars` cases; `report_flags` from a hand-built `EffectiveConfig(options=...)`; sections for
skips, warnings, `--durations=3` (3 slowest across stages), `--durations=0`, hidden-count line with
`--durations-min` default and user value; empty-result lines for `-r s`, `--report-chars=s`, `-rsw`; config-set
flags print nothing when empty except `--durations`; `--durations=0` with more rows than the budget left → the
first (slowest) rows are shown, then `(N more rows not shown, budget used up.)`; the same for a long `-rs` list;
with `-rs`, `-rw` and `--durations` all over budget each section shows its first rows (even share).
