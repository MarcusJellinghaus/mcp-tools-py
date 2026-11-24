# Step 8 — Hint line and flag notes

## LLM prompt
Read `pr_info/steps/summary.md` (design changes 4 and 7) and this file; issue #293 D7, D10, D11, D21, D22 and the
`--snapshot-update` / `--durations-min` rows define the behaviour. Implement test-first. Run pylint, mypy and the
non-integration pytest suite. One commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/report_extras.py`
- Tests: `tests/test_code_checker_pytest/test_report_extras.py`

## WHAT
```python
SLOW_RUN_SECONDS = 10.0
SNAPSHOT_NOTE = "--snapshot-update was passed: baselines may have been rewritten; check git status."
DURATIONS_MIN_NOTE = "--durations-min has no effect without --durations."

def hint_line(report: PytestReport, flags: ReportFlags) -> str | None: ...
def flag_notes(flags: ReportFlags) -> list[str]: ...
```

## ALGORITHM
```
hint_line:
    allowed = {"s","w"} - ({"w"} if disable_warnings); in_effect = flags.letters & allowed
    applicable = ({"s"} if folded_skips) | ({"w"} if warnings and not disable_warnings)
    parts, why = [], []
    if applicable - in_effect: letters = "".join(c for c in "sw" if c in applicable | in_effect)
        parts += [f'"-r{letters}"']; why += ["skip reasons" if "s" in letters, "warnings — counted only by default" if "w" in letters]
    if flags.durations is None and (parts or stage_seconds(report) > SLOW_RUN_SECONDS): parts += ['"--durations=5"']; why += ["slowest tests"]
    return f"For details: extra_args=[{', '.join(parts)}] ({', '.join(why)})" if parts else None
flag_notes:
    no_effect → f"-r{no_effect} has no effect here; supported: -rs, -rw (failures are always shown; -s shows passing-test output)"
    durations_min_in_call and durations is None → DURATIONS_MIN_NOTE;  snapshot_update → SNAPSHOT_NOTE
```

## DATA
- Skips + warnings, no flags → `For details: extra_args=["-rsw", "--durations=5"] (skip reasons, warnings — counted only by default, slowest tests)`.
- `addopts = -rs` + warnings → `-rsw`. `-rsw` in effect + fast run → `None`.
- Clean fast run → `None`; clean run with stage sum 11 s → `["--durations=5"] (slowest tests)`.
- `--disable-warnings` + only warnings → no `-r` part.

## Tests (write first)
Cases above; `-ra` in effect counts as `s`+`w`; `-rx` in effect is never carried into the hint; notes for `-rxp`,
`-rz`, `--durations-min` without `--durations`, `--snapshot-update` from any source.
