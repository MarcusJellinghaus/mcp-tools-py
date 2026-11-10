# Step 14 — Documentation

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_14.md`).
Write the docs, check that every link resolves, run pylint, pytest (`-n auto`,
`-m "not integration"`) and mypy, run `run_format_code`, and make one commit.

## WHERE
- New: `docs/architecture/output-conventions.md`
- Modified: `docs/architecture/architecture.md`, and the module docstring of
  `src/mcp_tools_py/utils/report_budget.py` (it should already name the doc; check it does)

## WHAT — `output-conventions.md`
- **Goals:** bounded, relevant first, honest, navigable (one line each).
- **Pipeline:** `runners` → `parsers` → `models` (full data, never truncated) →
  `reporting` (all reduction happens here) → global guard (safety net only).
- **Shared module:** `utils/report_budget.py` — the limits table (GUARD_*, LINE_CHARS,
  TOOL_*, LOCATIONS_PER_RULE, LINES_PER_LOCATION, SUMMARY_TOP, MAX_FAILURES, FAILED_IDS,
  MAX_COLLECTOR_IDS, ERROR_TAIL_LINES, HINT_LINES), plus `bound_text`, `guard_output`,
  `Location`, `render_locations` and `render_summary`. Per-tool budgets sit below the
  guard; the guard firing on routine output is a bug. Caps that only shape one tool's own
  output (the coverage digest) may stay local.
- **Checklist for a new tool:** the 10 items from issue #60, using the real function names:
  1. Parse output into models; unparseable modes pass through.
  2. Start with `format_total_line`.
  3. Group by rule/kind; sort by severity, then count.
  4. Offer `max_issues` (`0` = counts only).
  5. `render_locations`.
  6. `render_summary`.
  7. Every cut ends with a real drill-in hint.
  8. Don't call the guard — `GuardedMCP` applies it.
  9. Toolkit: keys from full data (line-insensitive); `fix_text` via `_result_from_findings`.
  10. One budget test per tool.
- **Toolkit:** keys are never truncated (rebase baseline); `fix_text` is bounded and `_merge`
  splits the budget across tools.

## HOW — `architecture.md`
- Checker Module Pattern: link to `output-conventions.md`; the `reporting.py` row links
  to it too. Fix the sentence saying vulture and tach are `runners.py` alone (they now
  have `parsers.py`/`reporting.py`; lint_imports still is).
- Module Overview: add a `utils/report_budget.py` entry; mention `GuardedMCP` in the
  `utils/mcp_protocols.py` and `server.py` entries.
- Solution strategy: "output is size-limited" → link to the new doc.
- Bump "Last Updated" and the version.

## ALGORITHM / DATA
None.

## Tests
None (docs only). Checks must still pass.
