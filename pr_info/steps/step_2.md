# Step 2: JSON Parser + Tests

> **Context**: Read `pr_info/steps/summary.md` first for full architecture overview.

## Prompt

```
Implement Step 2 of Issue #149 (bandit security linter).
Read pr_info/steps/summary.md for architecture context, then read this step file.

Create the bandit JSON parser and its tests. Follow the pattern from
code_checker_ruff/parsers.py but handle bandit's dict-based JSON structure
(top-level keys: results, errors, metrics, generated_at) instead of ruff's array.

Reference tests/test_code_checker_ruff/test_parsers.py for test structure.

After implementation, run all three code quality checks (pylint, pytest, mypy)
using MCP tools with the recommended fast unit test exclusions.
Commit: "feat(bandit): add JSON parser with tests"
```

## WHERE

- **Create**: `src/mcp_tools_py/code_checker_bandit/parsers.py`
- **Create**: `tests/test_code_checker_bandit/__init__.py`
- **Create**: `tests/test_code_checker_bandit/test_parsers.py`
- **Modify**: `src/mcp_tools_py/code_checker_bandit/__init__.py` — add re-export

## WHAT

### `parsers.py`

```python
def parse_bandit_json_output(
    raw_output: str,
    project_dir: str,
) -> tuple[list[BanditMessage], list[str], str | None]:
    """Parse bandit --format json output into BanditMessage objects.

    Returns:
        Tuple of (messages, file_errors, parse_error_string_or_none)
    """
```

### ALGORITHM

```
1. Return ([], [], None) if raw_output is empty/whitespace
2. json.loads(raw_output) → expect dict with "results" and "errors" keys
3. If not dict → return ([], [], "Expected JSON object...") 
4. Extract data["errors"] → format each dict as "filename: reason" → list[str]
5. For each item in data["results"]:
     - normalize filename via os.path.relpath(filename, project_dir)
     - extract cwe_id and cwe_link from item["issue_cwe"] dict
     - build BanditMessage
6. Return (messages, file_errors, None)
```

### DATA

**Input**: Bandit JSON structure:
```json
{
  "errors": [{"filename": "bad.py", "reason": "syntax error"}],
  "results": [{
    "test_id": "B101", "test_name": "assert_used",
    "issue_severity": "LOW", "issue_confidence": "HIGH",
    "issue_text": "Use of assert detected.",
    "filename": "/abs/path/src/foo.py",
    "line_number": 10, "col_offset": 0, "end_col_offset": 15,
    "line_range": [10], "more_info": "https://...",
    "issue_cwe": {"id": 703, "link": "https://cwe.mitre.org/..."},
    "code": "9 \n10 assert x > 0\n11 \n"
  }],
  "metrics": { ... },
  "generated_at": "2024-01-01T00:00:00Z"
}
```

**Output**: `tuple[list[BanditMessage], list[str], str | None]`

- `list[BanditMessage]` — parsed results
- `list[str]` — file-level error strings (formatted as "filename: reason")
- `str | None` — parse error message if JSON parsing failed

### Tests (`test_parsers.py`)

Mirror `test_code_checker_ruff/test_parsers.py` structure:

| Test | What it validates |
|------|-------------------|
| `test_parse_valid_json_with_results` | Full bandit JSON → correct BanditMessage fields |
| `test_parse_valid_json_with_errors` | `errors` array → extracted as strings |
| `test_parse_empty_output` | Empty string → `([], [], None)` |
| `test_parse_empty_results_array` | Valid JSON, empty results → `([], [], None)` |
| `test_parse_invalid_json` | Bad JSON → parse error string |
| `test_parse_array_instead_of_object` | JSON array → error "Expected JSON object" |
| `test_parse_paths_normalized` | Absolute paths → relative via `os.path.relpath` |
| `test_parse_missing_cwe_fields` | Missing `issue_cwe` → defaults (0, "") |
| `test_parse_very_long_invalid_output` | 300+ char bad input → truncated error message |

Use a `_make_bandit_result_item()` helper (like ruff's `_make_ruff_item()`) for building test JSON dicts.

## HOW

- Import `BanditMessage` from `.models`
- Use `json.loads`, `os.path.relpath` — same as ruff parser
- No external dependencies beyond stdlib
