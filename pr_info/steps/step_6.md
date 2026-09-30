# Step 6 — Mypy hint parsing

## LLM prompt

Read `pr_info/steps/summary.md`, then implement this step (`pr_info/steps/step_6.md`) only.
Tests first. Run pylint, pytest (`-n auto`), mypy; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_mypy/models.py` — `MypyMessage`
- `src/mcp_tools_py/code_checker_mypy/parsers.py` — `parse_mypy_json_output`
- `tests/test_code_checker_mypy/test_parsers.py`, `test_models.py`, `test_reporting.py` (`test_mypy_result_methods` only)

## WHAT

```python
class MypyMessage(NamedTuple):
    ...
    code: str | None = None
    hint: str | None = None  # notes attached to this error, newline-separated
```

## HOW

Parser adds `hint=data.get("hint")`. Nothing else changes; reporting uses it in step 7.

## DATA

Mypy JSON line: `{"file": "a.py", "line": 3, "column": 4, "message": "...", "hint": "Line 1\nLine 2",
"code": "arg-type", "severity": "error"}` → `MypyMessage(..., hint="Line 1\nLine 2")`.

## Tests

- Parser reads `hint`; missing/`null` hint → `None`.
- Rewrite tests that assume null-coded notes (real notes always have a code):
  - `test_parsers.py::test_parse_mypy_json_output_with_empty_lines` — note gets `"code": "misc"`.
  - `test_models.py::test_mypy_message_optional_code` — test `hint` defaults to `None` with a coded note.
  - `test_models.py::test_mypy_result_get_error_codes` and `test_mypy_result_get_messages_by_severity`,
    `test_reporting.py::test_mypy_result_methods` — give notes a code and adjust expected sets.
