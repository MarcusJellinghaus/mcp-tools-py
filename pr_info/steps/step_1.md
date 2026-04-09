# Step 1: Models and Parsers (with tests)

> **Context**: See `pr_info/steps/summary.md` for the full plan. This is step 1 of 5.

## Goal

Create the foundational data layer: `RuffMessage` and `RuffResult` models, plus the JSON parser that converts ruff's `--output-format=json` output into these models.

## LLM Prompt

```
Read pr_info/steps/summary.md for full context, then implement step 1.

Create the code_checker_ruff package with models and parsers. Follow TDD:
write tests first in tests/test_code_checker_ruff/, then implement.
Mirror the pylint pattern (see code_checker_pylint/models.py and parsers.py)
but keep it simpler — flat NamedTuples, os.path.relpath for path normalization.

After implementation, run all three code quality checks (pylint, pytest, mypy).
Fix any issues before committing.
```

## WHERE

**Create:**
- `src/mcp_tools_py/code_checker_ruff/__init__.py`
- `src/mcp_tools_py/code_checker_ruff/models.py`
- `src/mcp_tools_py/code_checker_ruff/parsers.py`
- `tests/test_code_checker_ruff/__init__.py`
- `tests/test_code_checker_ruff/test_parsers.py`

## WHAT

### `models.py` — Data structures

```python
class RuffMessage(NamedTuple):
    code: str           # e.g. "D100", "E501"
    message: str        # human-readable description
    filename: str       # relative path (normalized from absolute)
    line: int
    column: int
    end_line: int
    end_column: int
    url: str            # link to ruff docs for this rule
    fixable: bool       # True if ruff can auto-fix this violation
    noqa_row: int       # line where # noqa would suppress this

class RuffResult(NamedTuple):
    return_code: int
    messages: list[RuffMessage]
    error: str | None = None
    raw_output: str | None = None
```

### `parsers.py` — JSON parsing

```python
def parse_ruff_json_output(
    raw_output: str,
    project_dir: str,
) -> tuple[list[RuffMessage], str | None]:
    """Parse ruff --output-format=json output into RuffMessage objects.
    
    Returns:
        Tuple of (messages, error_message_or_None)
    """
```

### `__init__.py` — Re-exports

```python
from mcp_tools_py.code_checker_ruff.models import RuffMessage, RuffResult
from mcp_tools_py.code_checker_ruff.parsers import parse_ruff_json_output

__all__ = ["RuffMessage", "RuffResult", "parse_ruff_json_output"]
```

## HOW

- Parser uses `json.loads()` on raw output
- Each JSON item has nested `location`/`end_location` dicts and `fix` dict — flatten into `RuffMessage` fields
- `fixable` = `bool(item.get("fix"))` — ruff only includes `fix` key when a fix exists
- Path normalization: `os.path.relpath(item["filename"], project_dir)` to convert absolute → relative
- Error handling mirrors `parse_pylint_json_output`: empty/whitespace → empty list, invalid JSON → error message, non-list → error

## ALGORITHM — `parse_ruff_json_output`

```
1. if raw_output is empty/whitespace: return ([], None)
2. json.loads(raw_output) → data; on JSONDecodeError return ([], error_msg)
3. if not isinstance(data, list): return ([], "Expected JSON array...")
4. for each item in data:
5.   extract fields, flatten location/end_location, derive fixable from fix presence
6.   normalize filename with os.path.relpath(filename, project_dir)
7.   append RuffMessage to results
8. return (results, None)
```

## DATA — Ruff JSON item structure (input)

```json
{
  "code": "D100",
  "message": "Missing docstring in public module",
  "filename": "/absolute/path/to/file.py",
  "location": {"row": 1, "column": 0},
  "end_location": {"row": 1, "column": 0},
  "fix": {
    "applicability": "safe",
    "message": "Add docstring",
    "edits": [...]
  },
  "noqa_row": 1,
  "url": "https://docs.astral.sh/ruff/rules/undocumented-public-module"
}
```

Note: `fix` key is absent when there is no auto-fix available.

## Tests — `test_parsers.py`

Test cases (mirror `test_code_checker_pylint/test_parsers.py` structure):
1. `test_parse_valid_json_output` — two violations, verify all fields extracted correctly
2. `test_parse_empty_output` — empty string → ([], None)
3. `test_parse_whitespace_only_output` — whitespace → ([], None)
4. `test_parse_empty_json_array` — "[]" → ([], None)
5. `test_parse_invalid_json` — bad string → ([], error)
6. `test_parse_json_object_instead_of_array` — dict → ([], error)
7. `test_parse_absolute_paths_normalized` — verify `/project/src/file.py` becomes `src/file.py`
8. `test_parse_fixable_detection` — item with `fix` key → `fixable=True`; without → `fixable=False`
9. `test_parse_missing_optional_fields` — item with minimal fields → defaults applied

## Commit

```
feat(ruff): add RuffMessage/RuffResult models and JSON parser

- RuffMessage NamedTuple with flat fields (code, message, filename, location, fixable, url)
- RuffResult NamedTuple matching PylintResult pattern
- parse_ruff_json_output() with absolute→relative path normalization
- Unit tests for parser covering valid/invalid/edge cases
```
