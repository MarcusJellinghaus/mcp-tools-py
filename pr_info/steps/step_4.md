# Step 4 — Skips: entries, folding, module-level count

## LLM prompt
Read `pr_info/steps/summary.md` (design changes 3 and 8) and this file; issue #293 D14, D20 and the "Data shape"
constraint define the behaviour. Implement test-first. Run pylint, mypy and the non-integration pytest suite.
One commit.

## WHERE
- `src/mcp_tools_py/code_checker_pytest/report_data.py`
- `src/mcp_tools_py/code_checker_pytest/reporting.py` (`get_test_summary`)
- Tests: `tests/test_code_checker_pytest/test_report_data.py` (all tests of this step, including the
  `get_test_summary` skip-count test). Do not add tests to `test_reporting.py` (714 lines; must stay under the
  750-line limit).

## WHAT
```python
@dataclass(frozen=True)
class SkipKey:
    path: str
    lineno: int | None
    reason: str

def folded_skips(report: PytestReport) -> list[tuple[int, SkipKey]]:
    """Skip entries of collectors, then tests, folded like pytest's _folded_skips."""

def skip_lines(folded: list[tuple[int, SkipKey]]) -> list[str]:
    """'SKIPPED [3] tests/x.py:12: reason' / 'SKIPPED [2] tests/x.py: reason'."""

def module_skip_count(report: PytestReport) -> int:
    """Distinct node IDs of skipped collectors."""

def skipped_count(report: PytestReport) -> int:
    """(summary.skipped or 0) + module_skip_count(report)."""
```
Private `_parse_skip(longrepr, root) -> tuple[str, int, str] | None`.

## HOW
`get_test_summary` uses `skipped_count(report)` for `⏭️ Skipped`. `Summary.skipped` is not changed (verdict
classification keeps reading it). `reporting.py` imports `report_data`; `report_data` must not import `reporting`.

## ALGORITHM
```
_parse_skip(longrepr, root):
    text = strip_xdist_header(longrepr); try path, lineno, msg = ast.literal_eval(text) except (ValueError, SyntaxError, TypeError): None
    return relative_path(path, root), lineno, msg.removeprefix("Skipped: ")
folded_skips: d = {}
    for collector with outcome "skipped" and parse ok: key (path, lineno, reason)
    for test with outcome "skipped": stage = first of setup/call with outcome "skipped"; parse its longrepr
        key lineno = None if stage is setup and "skip" in keywords and "pytestmark" not in keywords
    d.setdefault(key, count) += 1; return [(count, key) ...] in insertion order
```

## DATA
- Module-level `pytestmark = pytest.mark.skip("r")`, 2 tests (keywords contain `skip`, not `pytestmark`) →
  `[(2, SkipKey("tests/test_a.py", None, "r"))]` → `SKIPPED [2] tests/test_a.py: r`.
- Two decorated `@pytest.mark.skip` tests (keywords contain `skip` and `pytestmark`) → two entries with line numbers.
- xfailed test (outcome `xfailed`, call stage outcome `skipped`) → not listed.

## Tests (write first)
Hand-built `PytestReport`s with longrepr strings shaped like the probe:
`"('C:\\\\proj\\\\tests\\\\test_a.py', 4, 'Skipped: r')"`, also with an `[gw0] …` first line; a collector skip;
an xfail; an unparseable longrepr (ignored); `get_test_summary` shows `⏭️ Skipped: 3` for 2 test skips plus 1
skipped collector.
