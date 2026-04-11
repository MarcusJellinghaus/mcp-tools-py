# Step 1: Data Models + Dependency

> **Context**: Read `pr_info/steps/summary.md` first for full architecture overview.

## Prompt

```
Implement Step 1 of Issue #149 (bandit security linter).
Read pr_info/steps/summary.md for architecture context, then read this step file.

Add the bandit dependency to pyproject.toml and create the data models module
with BanditMessage and BanditResult. Create the package __init__.py.
Follow existing patterns from code_checker_ruff/models.py and code_checker_mypy/models.py.

After implementation, run all three code quality checks (pylint, pytest, mypy)
using MCP tools with the recommended fast unit test exclusions.
Commit: "feat(bandit): add data models and dependency"
```

## WHERE

- **Modify**: `pyproject.toml` — add dependency
- **Create**: `src/mcp_tools_py/code_checker_bandit/__init__.py` — empty initially
- **Create**: `src/mcp_tools_py/code_checker_bandit/models.py` — data models

## WHAT

### `pyproject.toml`

Add `"bandit>=1.7.0"` to `[project.dependencies]` list (after `ruff>=0.9.0`).

### `models.py`

```python
class BanditMessage(NamedTuple):
    test_id: str        # e.g. "B101"
    test_name: str      # e.g. "assert_used"
    issue_severity: str  # "HIGH", "MEDIUM", "LOW"
    issue_confidence: str  # "HIGH", "MEDIUM", "LOW"
    issue_text: str     # human-readable description
    filename: str       # relative path
    line_number: int
    more_info: str      # URL to bandit docs
    cwe_id: int         # e.g. 703
    cwe_link: str       # e.g. "https://cwe.mitre.org/data/definitions/703.html"

class BanditResult(NamedTuple):
    return_code: int
    messages: list[BanditMessage]
    errors: list[str]              # file-level errors (syntax errors, etc.)
    error: str | None = None       # execution/parse error
    raw_output: str | None = None
```

### `__init__.py`

Re-export `BanditMessage` and `BanditResult` (will grow as later steps add parsers/runners/reporting).

## DATA

- `BanditMessage`: 10 fields — only what reporting actually uses (no `col_offset`, `end_col_offset`, `line_range`, `code` snippet)
- `BanditResult`: mirrors `PylintResult`/`MypyResult` pattern with added `errors: list[str]` for bandit's file-level errors array
- `errors` defaults to `[]` via empty list — NamedTuple with default

## Notes

- No tests in this step — models are NamedTuples with no logic to test
- The `__init__.py` will be updated in each subsequent step to re-export new public API
