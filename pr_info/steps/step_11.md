# Step 11 — tach structured output

## LLM prompt
Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_11.md`).
Probe the real JSON shape first, then write the tests, then the code. Run pylint, pytest
(`-n auto`, `-m "not integration"`) and mypy until they pass, run `run_format_code`, and
make one commit.

## Precondition: probe the JSON shape
Write `.scratch/test_tach_probe.py`. It creates a tmp project with `tach.toml` declaring
two modules, one undeclared import and one deprecated/warning case if tach supports it.
It then runs `tach check --output json` from the tool env (locate it the way
`ToolContext.tool_environment.binary("tach")` does) and prints stdout, stderr and the
return code. Run it with
`run_pytest_check(extra_args=["-p", "no:cacheprovider", "-s", ".scratch/test_tach_probe.py"])`.
Copy the real outputs into test fixtures, then delete `.scratch/`.
If the tach binary is unavailable, or the output is not JSON, write one line to
`pr_info/.blocked.txt` and stop.

## WHERE
- New: `src/mcp_tools_py/code_checker_tach/parsers.py`, `reporting.py`
- Modified: `code_checker_tach/runners.py`, `code_checker_tach/__init__.py`,
  `checker_tools/tach_tool.py`, `toolkit_checks.py` (`_run_tach`)
- New tests: `tests/test_code_checker_tach/test_parsers.py`, `test_reporting.py`; update
  the existing tach tests; put the toolkit tach tests in a new `tests/test_toolkit_check_tach.py`

## WHAT
```python
# parsers.py
class TachDiagnostic(NamedTuple):
    file: str | None
    line: int | None
    severity: str             # "error" | "warning" (lower-cased from the JSON)
    kind: str                 # e.g. "UndeclaredDependency"
    usage_module: str | None
    dependency: str | None    # definition module / import path
    message: str              # f"{kind}: {usage_module} -> {dependency}" or tach's own text

def parse_tach_json(stdout: str) -> list[TachDiagnostic] | None   # None = unknown shape / {"error": ...}

# runners.py
class TachResult(NamedTuple):
    error: str | None          # timeout / failed to run
    return_code: int
    diagnostics: list[TachDiagnostic]
    raw: str | None            # combined output when it could not be parsed

def run_tach_check(tach_binary, project_dir, timeout_seconds) -> TachResult

# reporting.py
TACH_HINT = "fix these and rerun"   # run_tach_check has no target_directories
def format_tach_report(result: TachResult, max_issues: int = 1) -> str
```

## ALGORITHM
```
parse: json.loads; walk the list; per item take the single wrapper key ("Located"/"Global"/...) → dict
       severity, file_path, line_number, details → first nested key = kind, fields usage_module/definition_module/import_mod_path
       anything that does not fit (incl. {"error": ...} dict, plain text) → return None
report: error → text; raw → status line + raw (pass-through); none → "tach check passed (no output)."
        status line from return code ("tach check passed" / "failed"), then format_total_line("tach", errors, groups)
        groups keyed (severity, kind, usage_module -> dependency), errors first, then by -count
        top max_issues → render_locations(Location(file, line, message), hint=TACH_HINT); rest → render_summary; warnings-only → "passed with N warnings"
```

## HOW
- Delete `format_tach_result`. The runner owns the command and timeout handling and
  returns a `TachResult`.
- `tach_tool.run_tach_check(max_issues: int = 1)` → `format_tach_report(result, max_issues)`.
  Update the docstring.
- `toolkit_checks._run_tach` calls the runner (its own `execute_command` is removed):
  - error → status error;
  - `raw` with a non-zero rc → keep the degraded single finding `tach|{depth}`, message `raw`;
  - `raw` with rc 0 → `status="ok"`, no findings, summary
    `f"tach check passed; unparsed output: {_one_line(bound_text(raw, max_lines=5))}"`;
  - otherwise findings only for `severity == "error"`, keyed
    `f"tach|{d.file}|{d.usage_module}|{d.dependency}"`, through `_result_from_findings`
    with `locations=[f"{d.file}:{d.line}"]`;
  - warnings are appended to the summary (`"; tach: N warning(s): <first messages>"`) and
    never become findings. With no errors the status is `ok`.

## DATA
See the WHAT section.

## Tests (write first)
- Parser against the probed fixtures; the `{"error": "..."}` dict and plain text → `None`.
- Report budget test: 500 synthetic errors across 40 module pairs → < `TOOL_LINES` lines,
  ends with `SUMMARY_HINT`; warnings-only → "passed"; the tool accepts `max_issues`.
- Toolkit: warnings-only → `status == "ok"` with no findings; two errors → two distinct keys;
  unparseable output with rc 0 → `status == "ok"`, no findings, summary contains
  "unparsed output".
- Report: the location overflow line ends with `TACH_HINT` and never mentions
  `target_directories`.
