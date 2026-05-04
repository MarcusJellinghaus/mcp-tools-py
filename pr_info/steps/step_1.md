# Step 1 — Build `code_checker_lint_imports` package (TDD)

## LLM Prompt

> Read `pr_info/steps/summary.md` for the overall design (state classification
> table, output layout, file list). Then implement **this step only**:
> create the new `code_checker_lint_imports` checker package and its tests,
> in TDD order. Do not touch `checker_tools.py`, `.importlinter`, `tach.toml`,
> or `tests/test_checker_tools.py` yet — that is step 2.
>
> After implementation, run `mcp__tools-py__run_pylint_check`,
> `mcp__tools-py__run_pytest_check` (with the standard `-n auto` exclusion
> pattern from CLAUDE.md), and `mcp__tools-py__run_mypy_check`. All three
> must pass before committing.

## WHERE — files to create

```
src/mcp_tools_py/code_checker_lint_imports/__init__.py
src/mcp_tools_py/code_checker_lint_imports/runners.py
tests/test_code_checker_lint_imports/__init__.py
tests/test_code_checker_lint_imports/test_runners.py
```

Mirror the shape of `code_checker_tach/` and `code_checker_vulture/`
(single `runners.py`, no separate `models`/`parsers`/`reporting` files).

## WHAT — public API

### `runners.py` — public entry point

```python
def run_lint_imports_check_impl(
    lint_imports_binary: str,
    project_dir: str,
    extra_args: list[str] | None = None,
) -> str:
    """Run lint-imports and return an LLM-optimised structured report.

    The first non-empty line is always either an info line (when flags
    were stripped) or the state header. Truncation cannot hide it.
    """
```

### `runners.py` — private helpers (unit-testable)

```python
_VERBOSE_FLAGS: tuple[str, ...] = ("-v", "--verbose")
MAX_OUTPUT_LINES: int = 300
_TRUNCATION_MARKER: str = (
    "[output truncated — run with --contract <name> for individual results]"
)

_SUMMARY_RE = re.compile(r"Contracts:\s+(\d+)\s+kept,\s+(\d+)\s+broken")
_BROKEN_LINE_RE = re.compile(r"^(?P<name>.+?)\s+BROKEN\s+\[", re.MULTILINE)
_WARNING_RE = re.compile(
    r"No matches for ignored import\s+\S.*?\.", re.DOTALL
)


def _strip_verbose_flags(
    extra_args: list[str] | None,
) -> tuple[list[str], bool]:
    """Return (cleaned_args, was_stripped)."""


def _parse_summary(combined: str) -> tuple[int, int] | None:
    """Return (kept, broken) or None if summary line not found."""


def _parse_broken_contracts(combined: str) -> list[str]:
    """Return ordered, de-duplicated list of broken contract names."""


def _parse_warnings(combined: str) -> list[str]:
    """Return list of warning sentences (whitespace-collapsed)."""


def _classify_state(
    return_code: int, summary: tuple[int, int] | None
) -> str:
    """Return 'PASSED', 'BROKEN', or 'ERROR'."""


def _format_report(
    state: str,
    summary: tuple[int, int] | None,
    broken_contracts: list[str],
    warnings: list[str],
    raw_body: str,
    info_line: str | None,
) -> str:
    """Assemble the final string and apply the line cap."""
```

### `__init__.py`

```python
"""Code checker package for running import-linter contract checks."""

from mcp_tools_py.code_checker_lint_imports.runners import (
    run_lint_imports_check_impl,
)

__all__ = ["run_lint_imports_check_impl"]
```

## HOW — integration points

- Imports: `from mcp_tools_py.utils.subprocess_runner import execute_command`
  and `from mcp_tools_py.log_utils import log_function_call`.
- Decorator: apply `@log_function_call` to `run_lint_imports_check_impl`
  (matches `run_bandit_check_impl`).
- Logger: `logger = logging.getLogger(__name__)`.
- No dependency on any other `code_checker_*` package — keeps
  `forbidden-imports` contract clean.

## ALGORITHM — `run_lint_imports_check_impl`

```
1. cleaned_args, stripped = _strip_verbose_flags(extra_args)
   info_line = "[Info: stripped --verbose/-v from extra_args]" if stripped else None
2. result = execute_command([binary, *cleaned_args], cwd=project_dir)
3. combined = (result.stdout + "\n" + result.stderr).strip("\n") if result.stderr
              else result.stdout
4. summary = _parse_summary(combined)
   broken = _parse_broken_contracts(combined)
   warnings = _parse_warnings(combined)
5. state = _classify_state(result.return_code, summary)
6. return _format_report(state, summary, broken, warnings, combined, info_line)
```

`_format_report` rules (line-capped, marker if exceeded):

```
- if info_line: emit it first
- emit "=== <STATE_HEADER> ===" where STATE_HEADER is one of:
    "PASSED"
    f"BROKEN: {broken_count} of {kept+broken} contracts failed"
    "ERROR: lint-imports output could not be parsed"
- if summary: emit "Contracts: N kept, M broken"
- if state == "BROKEN" and broken: emit "Broken contracts:" + bulleted names
- if warnings: emit "Warnings:" + bulleted lines
- emit blank line, then raw_body
- if total lines > MAX_OUTPUT_LINES: keep first MAX_OUTPUT_LINES lines
  and append _TRUNCATION_MARKER
```

## DATA — return value

A single `str`. First non-empty line is always the info line (if present)
or the state header. Empty subprocess output yields a state header followed
by a body of `(no output)` — never returns an empty string.

## Tests — `tests/test_code_checker_lint_imports/test_runners.py`

Each fixture is an inline Python triple-quoted string preceded by a comment
giving the import-linter version it was captured from and the capture date,
e.g.:

```python
# Captured from import-linter 2.x on 2026-05-04 (clean run, this repo).
CLEAN_OUTPUT = """\
... contracts ...
Contracts: 3 kept, 0 broken.
"""
```

Test classes (one per parsed concern, plus orchestrator):

1. `TestStripVerboseFlags` — strips `-v` and `--verbose`, leaves others alone,
   reports `was_stripped=True` only when something was removed, handles None.
2. `TestParseSummary` — clean case; broken case; missing line returns None;
   numbers larger than one digit.
3. `TestParseBrokenContracts` — extracts one, multiple, none; preserves order;
   ignores `KEPT` lines; de-duplicates if a name appears twice.
4. `TestParseWarnings` — extracts single warning; multiple warnings;
   warnings interleaved between progress lines (issue's reproduction case).
5. `TestClassifyState` — full 3×3 truth table: rc 0/non-zero × summary
   parsed-clean / parsed-broken / None.
6. `TestFormatReport` — info line on top; state header on top when no info
   line; summary line present; broken list present in BROKEN state;
   warnings always included; line cap appends marker; ERROR fallback shape
   (header + raw body, no summary, no broken list).
7. `TestRunLintImportsCheckImpl` (orchestrator, mocks `execute_command`):
   - clean run → output starts with `=== PASSED ===`
   - broken run (rc=1, summary says `1 broken`) → starts with
     `=== BROKEN: 1 of N contracts failed ===` and lists the broken name
   - rc != 0 with no summary → `=== ERROR: ... ===` with raw body underneath
   - `extra_args=["--verbose"]` → info line above state header AND
     `--verbose` not present in the command passed to `execute_command`
   - long output → truncation marker present at end
   - empty output → no crash; returns header + `(no output)` body

Use `tests.conftest.make_command_result` and patch
`mcp_tools_py.code_checker_lint_imports.runners.execute_command`,
matching the pattern in `tests/test_code_checker_tach/test_runners.py`.

## Done When

- Files above exist with the listed signatures.
- All new tests pass.
- `mcp__tools-py__run_pylint_check`, `mcp__tools-py__run_pytest_check`
  (with the CLAUDE.md exclusion pattern), and `mcp__tools-py__run_mypy_check`
  all pass.
- One commit: `feat: add code_checker_lint_imports package (#171)`.
