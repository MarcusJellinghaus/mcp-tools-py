# Step 1 — Strict ruff parser

## LLM prompt

Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_1.md`.
Write the tests first, then the implementation. Run pylint, pytest
(`-n auto -m "not integration"`) and mypy; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/utils/ruff_parsing.py`
- `tests/test_code_checker_ruff/test_parsers.py`

## WHAT

```python
def _invalid_reason(item: object) -> str | None:
    """Why a ruff JSON entry cannot be used as a violation, or None if valid."""

def parse_ruff_json_output(raw_output: str, project_dir: str
) -> tuple[List[RuffMessage], str | None]   # signature unchanged
```

## HOW

- Called once per array item inside `parse_ruff_json_output`, replacing the
  current "skip non-dict" branch.
- Shared with `formatter/ruff_runner.py`; its fixtures (`unformatted`,
  `invalid-syntax`, `code: None`) must keep passing unchanged.

## ALGORITHM

```
_invalid_reason(item):
    if not dict: return "entries that are not objects"
    if "code" not in item or item.get("message") is None or item.get("filename") is None:
        return "entries without code, message or filename"
    loc = item.get("location"); row/col = loc.get(...) if dict
    if row or col is not an int (bool excluded): return "entries without locations"
    return None

parse loop:
    reason = _invalid_reason(item)
    if reason: return [], f"ruff returned {reason} (keys: {keys}); an argument in extra_args probably changed the output shape."
    build RuffMessage; code = item["code"] or "invalid-syntax"
```

`keys` = `", ".join(item)` for a dict, else `type(item).__name__`.

Optional fields read with `or` defaults so `null` is accepted:
`url=item.get("url") or ""`, `noqa_row=item.get("noqa_row") or -1`,
`end_location=item.get("end_location") or {}`, `fixable=bool(item.get("fix"))`.

## DATA

- Valid input: `(list[RuffMessage], None)` as today.
- Invalid entry: `([], "<error string>")` — no partial results.

## Tests (write first)

- `test_statistics_output_is_error` — feed the issue's `--statistics` JSON
  (`code`, `name`, `count`, `fixable`, `fixable_count`); assert `messages == []`,
  error mentions "without locations" and "extra_args".
- `test_non_dict_entry_is_error` — `[_make_ruff_item(), 42]` → error.
- `test_missing_location_row_is_error` / `test_non_int_column_is_error`.
- `test_missing_message_is_error` / `test_missing_filename_is_error`.
- `test_invalid_syntax_entry_with_nulls_parses` — `code="invalid-syntax"`,
  `url=None`, `noqa_row=None`, `fix=None`, `cell=None` → one message, `url == ""`.
- `test_null_code_normalised` — `code: None` → `code == "invalid-syntax"`.
- Rewrite `test_parse_missing_optional_fields`: `[{"code": "X001", "message": "test"}]`
  now returns an error and no messages.
