# Summary — Per-rule counts with a directory split (#237)

## Goal

`run_ruff_check`, `run_pylint_check`, `run_bandit_check` and `run_mypy_check` reports start with one
total line and show, for every rule, a name and a split of its count by top-level directory.
`max_issues=0` is the counts-only mode (no new parameter). Mypy gains `max_issues`, hint display and a
`Notes` section.

## Prerequisite

Rebase onto #236 (strict ruff/pylint/bandit parsers, bandit CWE line, ruff null `url`) before step 1.
After #236, required fields (ruff `filename`, pylint `path`, bandit `filename`) are always present, and
ruff `url` may be `None`.

## Architectural / design changes

- **New shared module `mcp_tools_py/utils/report_counts.py`.** The `code_checker_*` packages are
  independent layers in `.importlinter` and cannot import each other; `utils` is the only layer all
  four may use. It holds three pure functions and no state:
  - `plural(count, word)` → `"1 issue"`, `"3 issues"`.
  - `format_dir_split(paths)` → `"(src: 11, tests: 2)"`. Private `_top_level_dir` maps each path to its
    top-level directory, `(root)` for project-root files, `(outside)` for absolute paths, `..` paths and
    pylint's `Command line`.
  - `format_total_line(tool, issues, rules)` → `"ruff found 143 issues across 8 rules"`.
- **Rule-line layout stays in each checker's `reporting.py`.** Each checker keeps its own sort order
  (ruff: prefix priority; pylint: severity; bandit: severity/confidence) except mypy, which now sorts by
  count descending, ties alphabetical.
- **Path handling in parsers.** Ruff and bandit keep the path unchanged when `os.path.relpath` raises
  `ValueError` (other drive). Bandit joins its relative path with `project_dir` before `relpath`, so the
  result no longer depends on the server's cwd.
- **Mypy header ownership moves into `create_mypy_prompt`.** It emits
  `"Mypy found type issues that need attention:"` only when errors+warnings > 0, followed by the total
  line. `CheckerTools._format_mypy_result` only maps `None` to the "no type errors" message; its
  `MYPY_FAILURE_PREFIX` check and import go away (failures and reports are both passed through).
- **Mypy model/parser.** `MypyMessage` gains `hint: str | None = None`; the parser reads the `hint`
  field. Standalone notes (`severity == "note"`) are separated in reporting, not in the parser.
- **Mypy `max_issues: int | None = None`**, resolved once:
  `limit = len(groups) if max_issues is None else max(0, max_issues)`.

## Output formats

Ruff (`max_issues=1`):
```
ruff found 143 issues across 8 rules

ruff found 119 issues with rule SIM117 multiple-with-statements (tests: 119).
<message>
Locations:
- tests/a.py:3:5

- SIM102 collapsible-if: 13 occurrences (src: 11, tests: 2)
```
Rule name = end of URL; code only when `url` is null/empty.

Pylint: total line first in every mode; detail prompts start with
`pylint found 12 issues with rule C0411 wrong-import-order (src: 10, tests: 2).`;
summary lines `- W0613 unused-argument: 4 occurrences (src: 4)`. `max_issues=0` footer and the
`--- N additional issue types ---` block stay.

Bandit: total line first (before "File errors"); header
`bandit found 3 issues with B101 assert_used (tests: 3) [severity: LOW, confidence: HIGH]`;
summary `- B101 assert_used (LOW): 3 occurrences (tests: 3)`. Errors-only run:
`bandit found 0 issues across 0 rules` then the File errors section.

Mypy:
```
Mypy found type issues that need attention:     <- only when issues > 0

mypy found 3 issues across 2 rules

**arg-type (2 issues) (src: 2)**
- src/a.py:1:2 - message
    hint line 1
    hint line 2

- misc: 1 occurrence (tests: 1)                 <- codes beyond max_issues

Notes:                                          <- standalone notes; omitted at max_issues=0
- src/a.py:9:1 - Revealed type is "int"

To fix these issues:                            <- only when issues > 0
...
```
Notes-only run: `mypy found 0 issues across 0 rules` + `Notes:` section. No messages at all → `None`.

## Files

Created:
- `src/mcp_tools_py/utils/report_counts.py`
- `tests/test_report_counts.py`

Modified:
- `src/mcp_tools_py/utils/ruff_parsing.py` — `ValueError` fallback
- `src/mcp_tools_py/code_checker_bandit/parsers.py` — join with `project_dir`, `ValueError` fallback
- `src/mcp_tools_py/code_checker_ruff/reporting.py`
- `src/mcp_tools_py/code_checker_pylint/reporting.py`
- `src/mcp_tools_py/code_checker_bandit/reporting.py`
- `src/mcp_tools_py/code_checker_mypy/models.py`, `parsers.py`, `reporting.py`
- `src/mcp_tools_py/checker_tools/__init__.py` — `_format_mypy_result`
- `src/mcp_tools_py/checker_tools/ruff_check_tool.py`, `pylint_tool.py`, `bandit_tool.py`, `mypy_tool.py` — docstrings; mypy `max_issues`
- `README.md`, `docs/architecture/architecture.md`, `tests/mcp_tools_py_manual/TEST_PLAN.md`
- Tests: `tests/test_code_checker_ruff/test_parsers.py`, `test_reporting.py`;
  `tests/test_code_checker_bandit/test_parsers.py`, `test_reporting.py`;
  `tests/test_code_checker_pylint/test_reporting.py`;
  `tests/test_code_checker_mypy/test_parsers.py`, `test_models.py`, `test_reporting.py`;
  `tests/test_checker_tools_formatting.py`, `tests/test_checker_tools.py`

Out of scope: `format_ruff_fix_report`.

## Steps

1. Shared helpers `utils/report_counts.py`
2. Parser path fixes (ruff `ValueError`, bandit cwd)
3. Ruff report
4. Pylint report
5. Bandit report
6. Mypy hint parsing
7. Mypy report
8. Mypy `max_issues` tool parameter and docs
