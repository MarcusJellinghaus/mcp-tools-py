# Step 10 — vulture structured output

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_10.md`).
Write the tests first, then the code. Run pylint, pytest (`-n auto`, `-m "not integration"`)
and mypy until they pass, run `run_format_code`, and make one commit.

## WHERE
- New: `src/mcp_tools_py/code_checker_vulture/parsers.py`, `reporting.py`
- Modified: `code_checker_vulture/runners.py`, `code_checker_vulture/__init__.py`,
  `checker_tools/vulture_tool.py`, `toolkit_checks.py` (`_run_vulture`)
- New tests: `tests/test_code_checker_vulture/test_parsers.py`, `test_reporting.py`; update
  the existing vulture runner/tool tests and the vulture tests in `tests/test_toolkit_check.py`
  (that file is at 726 lines: move the vulture tests into a new
  `tests/test_toolkit_check_vulture.py`)

## WHAT
```python
# parsers.py
class VultureMessage(NamedTuple):
    file: str          # "/" separators
    line: int
    kind: str          # "unused function", or the full message for unnamed kinds
    name: str | None   # None for "unreachable code after '<stmt>'" / "unsatisfiable '<x>' condition"
    message: str       # e.g. "unused function 'foo'"
    confidence: int

def parse_vulture_output(text: str) -> tuple[list[VultureMessage], list[str]]  # (messages, unparsed lines)

# runners.py
class VultureResult(NamedTuple):
    error: str | None              # timeout / failed to run
    messages: list[VultureMessage]
    unparsed: list[str]

def run_vulture_check(...same args...) -> VultureResult

# reporting.py
VULTURE_HINT = "narrow target_directories, raise min_confidence, or fix these and rerun"
def format_vulture_report(result: VultureResult, max_issues: int = 1) -> str
```

## ALGORITHM
```
LINE_RE = r"^(?P<file>.+?):(?P<line>\d+): (?P<msg>.+?) \((?P<conf>\d+)% confidence(?:, \d+ lines?)?\)$"
NAMED_RE = r"^(?P<kind>unused [a-z ]+?) '(?P<name>[^']+)'$"
for each non-blank stripped line: m = LINE_RE match → kind/name from NAMED_RE, else kind=msg, name=None; file → "/"
                                  no match → unparsed
report: error → error text; no messages and unparsed → raw unparsed text (pass-through, e.g. --make-whitelist)
        no messages → "vulture found no issues."; else total line, groups by kind sorted (-max confidence, -count)
        top max_issues → header + render_locations(Location(file, line, message), VULTURE_HINT); rest → render_summary
        unparsed lines (if any) → "Unparsed vulture output:" + lines
```

## HOW
- The runner does the command build and timeout handling it does today, then calls the
  parser on stdout + stderr. The error strings ("vulture timed out after N seconds.",
  "vulture failed to run: ...") move into `VultureResult.error`.
- `vulture_tool.run_vulture_check` adds `max_issues: int = 1`, passes it to
  `format_vulture_report`, and updates its docstring.
- `__init__.py` exports `run_vulture_check`, `VultureResult`, `format_vulture_report`.
- `toolkit_checks._run_vulture` drops the string sentinels:
  - `result.error` → `ActionResult(status="error", summary=result.error)`;
  - no messages and unparsed lines → `status="error"`, summary `bound_text` of the
    unparsed text;
  - otherwise `_result_from_findings(None, findings, "vulture found no issues.", f"vulture found {n} issue(s).", locations=[f"{m.file}:{m.line}" ...])`,
    with findings keyed `f"vulture|{m.file}|{m.kind}|{m.name or m.message}"`,
    `rule=m.kind`, `path=m.file`.

## DATA
See the WHAT section. Keys are line-insensitive.

## Tests (write first)
- Parser: every kind (unused import/function/class/method/variable/attribute/property,
  unreachable code after 'return', unsatisfiable 'if'/'while'/'ternary' condition), the
  `, 3 lines` suffix, a Windows path `C:\x\a.py:12: ...` (normalised to `/`), and mixed
  stderr lines going to `unparsed`.
- Report budget test: 2000 messages across 6 kinds in 100 files → < `TOOL_LINES` lines,
  the location overflow line ends with `VULTURE_HINT`; 30 kinds → ends with `SUMMARY_HINT`;
  whitelist-style output passes through raw.
- Toolkit: keys are unique per name and do not change when line numbers shift; timeout →
  error status.
