# Tool Output Conventions

Every text that reaches an LLM — MCP tool responses and `PythonToolkit`'s
`ActionResult.fix_text` — follows these conventions. See
[architecture.md](architecture.md) for the surrounding structure.

## Goals

- **Bounded** — no response exceeds a known line and character budget.
- **Relevant first** — the total, then the largest or most severe groups, then detail.
- **Honest** — every cut is counted and named (`[... N lines / M chars omitted ...]`, `... and N more rules`).
- **Navigable** — every cut ends with a drill-in hint naming a real parameter, a sibling tool call, or a concrete narrowing action.

## Pipeline

```
runners → parsers → models → reporting → global guard
```

- **`runners`** execute the tool and hand raw output to the parser.
- **`parsers`** turn raw output into models.
- **`models`** hold the full data and are never truncated.
- **`reporting`** is where all reduction happens: grouping, capping, hints.
- **Global guard** (`guard_output`, applied by `GuardedMCP`) is a safety net only.

Toolkit `Finding` keys are built from the models, so they also see the full data.

## Shared module: `utils/report_budget.py`

All shared limits and the truncation primitives live in
[`src/mcp_tools_py/utils/report_budget.py`](../../src/mcp_tools_py/utils/report_budget.py).

| Limit | Value | Meaning |
|-------|-------|---------|
| `GUARD_LINES` / `GUARD_CHARS` | 400 / 24 000 | Global guard on every tool response |
| `LINE_CHARS` | 500 | Per-line cap applied by `bound_text` |
| `TOOL_LINES` / `TOOL_CHARS` | 300 / 16 000 | Per-tool budget (pytest, lint-imports, toolkit `fix_text`) |
| `LOCATIONS_PER_RULE` | 10 | Location rows per rule in `render_locations` |
| `LINES_PER_LOCATION` | 10 | Line numbers per row before `(+N)` |
| `SUMMARY_TOP` | 20 | Rule rows in `render_summary` |
| `MAX_FAILURES` | 10 | pytest failures rendered in detail |
| `FAILED_IDS` | 50 | Failed test IDs listed without detail |
| `MAX_COLLECTOR_IDS` | 10 | Further node IDs named for one pytest collection error |
| `ERROR_TAIL_LINES` | 50 | Tail kept from a pytest error's raw output |
| `HINT_LINES` | 5 | Hint lines shown under one mypy message |

Functions and types:

- **`bound_text(text, max_lines, max_chars, hint, keep)`** — caps each line, keeps head
  and tail (or only the tail with `keep="tail"`), replaces the middle with a counted
  marker, balances a code fence left open at the cut, and ends with `hint`.
- **`guard_output(text)`** — `bound_text` at the guard limits with `GUARD_HINT`.
- **`Location`** — one finding location: `path`, `line`, `message`, `details`.
- **`render_locations(items, hint)`** — rows grouped by (path, message), such as
  `- f.py: 57, 63, 73 (+12) — <message>`, capped at `LOCATIONS_PER_RULE` with a count
  line naming `hint`.
- **`render_summary(rows, title, top, hint, detail_hint)`** — top `SUMMARY_TOP` rule
  rows, then `... and N more rules (M occurrences), largest: ...` and the hint.
  `top=None` lists every row (`max_issues=0`).

Per-tool budgets sit below the guard. The guard firing on routine output is a bug in
that tool's reporting. Caps that only shape one tool's own output (the pytest coverage
digest) may stay local to that tool.

## Checklist for a new tool

1. Parse output into models; unparseable output modes pass through raw (bounded by the guard).
2. Start the report with `format_total_line` (`utils/report_counts.py`).
3. Group findings by rule or kind; sort by severity, then count.
4. Offer `max_issues` (`0` = counts only).
5. Render locations with `render_locations`.
6. Render the remaining rules with `render_summary`.
7. Every cut ends with a real drill-in hint.
8. Don't call the guard — `GuardedMCP` applies it to every registered tool.
9. Toolkit: build `Finding` keys from the full data, line-insensitive; produce
   `fix_text` via `_result_from_findings`.
10. Add one budget test: a large synthetic result stays within budget and ends with the hint.

## Toolkit

- **Keys are never truncated.** mcp-coder's rebase baseline compares key sets, so keys
  come from the full models.
- **`fix_text` is bounded.** `_result_from_findings` renders findings grouped by rule
  and bounds the text at `TOOL_LINES` / `TOOL_CHARS`. `_merge` splits that budget evenly
  across the results that carry a `fix_text`.
