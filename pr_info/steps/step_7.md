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
    if "s" in sections and folded: out.named("skip reasons (-rs)", "Skip reasons:\n" + skip_lines)
    if "w" in sections and groups: out.named("warnings (-rw)", "Warnings:\n" + warning lines)
    if durations is not None: cut = all if 0 else first N; shown = >= min; out.named("durations", header + rows + hidden line)
    if r_label: empties = ["no skipped tests" if s & none, "no warnings" if w & none]; if empties: out.add(f"{r_label}: {', '.join(empties)}.")
    return out.text()
```
Duration row: `f"{d.seconds:.2f}s {d.when} {d.nodeid}"`; hidden line:
`f"({hidden} durations < {flags.durations_min:g}s hidden; pass --durations-min=0 to show them.)"`.
`--durations` value not an int → treat as not in effect.

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
flags print nothing when empty except `--durations`; a tiny budget names the dropped sections in the notice.
