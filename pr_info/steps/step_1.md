# Step 1 — Shared limits, `bound_text`, global guard

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_1.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- New: `src/mcp_tools_py/utils/report_budget.py`
- Modified: `src/mcp_tools_py/utils/mcp_protocols.py` (add `GuardedMCP`)
- Modified: `src/mcp_tools_py/server.py`
- New tests: `tests/test_report_budget.py`, `tests/test_output_guard.py`

## WHAT

`report_budget.py` (module docstring: "Shared output budget: limits, truncation and the
global guard. See docs/architecture/output-conventions.md."):

```python
GUARD_LINES = 400
GUARD_CHARS = 24_000
LINE_CHARS = 500
TOOL_LINES = 300
TOOL_CHARS = 16_000
LOCATIONS_PER_RULE = 10   # location rows per rule (used from step 3)
LINES_PER_LOCATION = 10   # line numbers per row (used from step 3)
SUMMARY_TOP = 20          # used from step 3
MAX_FAILURES = 10         # used from step 7
FAILED_IDS = 50           # used from step 7
MAX_COLLECTOR_IDS = 10    # used from step 8
ERROR_TAIL_LINES = 50     # used from step 8
GUARD_HINT = "Output was cut: narrow the request (fewer targets, a smaller selection) to see the rest."

def bound_text(
    text: str,
    max_lines: int = TOOL_LINES,
    max_chars: int = TOOL_CHARS,
    hint: str | None = None,
    keep: Literal["both", "tail"] = "both",
) -> str: ...

def guard_output(text: str) -> str:
    return bound_text(text, GUARD_LINES, GUARD_CHARS, hint=GUARD_HINT)
```

Only add a constant in the step that first uses it. The comments above show
where each one comes in. Step 1 adds `GUARD_*`, `LINE_CHARS`, `TOOL_*` and
`GUARD_HINT`.

`mcp_protocols.py`:

```python
GUARD_ATTR = "__output_guarded__"

class GuardedMCP:
    """FastMCPProtocol wrapper whose tool() bounds every string a tool returns."""
    def __init__(self, mcp: FastMCPProtocol) -> None: ...
    def tool(self) -> ToolDecorator: ...
    def run(self) -> None: ...   # delegates
```

## HOW
- `tool()` gets the real decorator from `self._mcp.tool()`. It then returns a decorator
  that wraps `func` with `functools.wraps` (so FastMCP's `inspect.signature` follows
  `__wrapped__` and the parameter schema stays the same), applies `guard_output` to
  `str` results only (the `search_library_files` dict passes through unchanged), sets
  `GUARD_ATTR = True` on the wrapper, and passes the wrapper to the real decorator.
- `ToolServer.__init__`: keep `self.mcp` as the raw FastMCP (needed for `run()`). Build
  `guarded = GuardedMCP(self.mcp)` and pass `guarded` to all six `register(...)` calls.
- Registrars are unchanged. `@mcp.tool()` is already above `@log_function_call`, so the
  guard is outermost and the logs keep the full output.
- `utils` imports nothing above it, which keeps the import-linter contracts intact.

## ALGORITHM (`bound_text`)
```
lines = [l if len(l) <= LINE_CHARS else l[:LINE_CHARS] + f" [line truncated: {len(l)} chars]" for l in text.splitlines()]
if len(lines) <= max_lines and len(joined lines) <= max_chars: return joined lines (no hint)
room = max_lines - 2 (marker + hint) - 2 (reserved: one closing fence for head, one reopening fence for tail)
head_n = 0 if keep == "tail" else room * 2 // 3; tail_n = room - head_n
head, tail = lines[:head_n], lines[len(lines) - tail_n:]
def fenced(head, tail): add "```" to the end of head if head has an odd number of lines starting with "```";
                        add "```" to the start of tail if tail does
out_head, out_tail = fenced(head, tail)
while chars(out_head + out_tail) + len(marker) + len(hint) + newlines > max_chars:
    drop head[-1] if len(head) > len(tail) else tail[0]; out_head, out_tail = fenced(head, tail)
return out_head + [f"[... {omitted_lines} lines / {omitted_chars} chars omitted ...]"] + out_tail + ([hint] if hint)
```
`omitted_*` counts the original lines/chars that are not in head or tail. The text is
returned unchanged (apart from per-line caps) when it is within budget. The two fence
lines are reserved up front and the char check runs on the fenced parts, so the result
never exceeds `max_lines` or `max_chars`, fences included.

## DATA
- `bound_text` returns a `str` of at most `max_lines` lines and `max_chars` chars.
- `GuardedMCP` satisfies `FastMCPProtocol` structurally.

## Tests (write first)
`tests/test_report_budget.py`:
- Short text is unchanged; a long single line gets the `[line truncated: N chars]` marker.
- 1000 lines: the result has ≤ `max_lines` lines, keeps the first and last lines,
  contains the marker with the correct omitted count, and ends with the hint.
- A char-heavy text stays ≤ `max_chars`.
- `keep="tail"` keeps no head lines.
- A cut inside a fenced block leaves an even number of fence lines in each part.
- A fenced block of 1000 char-heavy lines cut with small limits (e.g. `max_lines=20`,
  `max_chars=2000`): the result, fences included, has ≤ `max_lines` lines and
  ≤ `max_chars` chars.

`tests/test_output_guard.py`:
- Build `ToolServer(tmp_path)` (copy the setup used in `tests/test_server_params.py`).
  For every tool in `server.mcp._tool_manager.list_tools()`, assert
  `getattr(tool.fn, GUARD_ATTR, False)`. Also assert the tool count is 19.
- A registered tool's input schema still lists its parameters (e.g. `run_mypy_check` has
  `max_issues`).
- A fake tool returning 2000 lines through `GuardedMCP` comes back ≤ `GUARD_LINES` lines
  and ends with `GUARD_HINT`; a dict return is unchanged.

Update existing tests that assert `register` receives `server.mcp` (e.g.
`tests/test_registrars.py`) to accept the `GuardedMCP` wrapper.

If FastMCP does not expose the wrapped signature (the schema test fails, and following
`__wrapped__` cannot fix it), write one line to `pr_info/.blocked.txt` and stop.
