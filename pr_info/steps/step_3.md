# Step 3 — Strict pylint parser

## LLM prompt

Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_3.md`.
Write the tests first, then the implementation. Run pylint, pytest
(`-n auto -m "not integration"`) and mypy; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_pylint/parsers.py`
- `tests/test_code_checker_pylint/test_parsers.py`

## WHAT

```python
def _invalid_reason(item: object) -> str | None:
    """Why a pylint JSON entry cannot be used as a message, or None if valid."""

def parse_pylint_json_output(raw_output: str
) -> tuple[List[PylintMessage], str | None]   # signature unchanged
```

## HOW

- Validate all items **before** the `logger.debug(... pylint_output[0].keys() ...)`
  call, which crashes on a non-dict first entry.
- Replace the "skip non-dict" branch; build `PylintMessage` from validated items
  (`item["path"]`, `item["line"]`, ...). Optional fields (`type`, `module`, `obj`,
  `message`) keep `item.get(..., "")`.

## ALGORITHM

```
_invalid_reason(item):
    if not dict: return "entries that are not objects"
    if any of path, symbol, message-id is missing or None:
        return "entries without path, symbol or message-id"
    if line or column is not an int (bool excluded): return "entries without locations"
    return None

parse: for item in list: reason -> return [], f"pylint returned {reason} (keys: {keys}); an argument in extra_args probably changed the output shape."
```

## DATA

- Valid input: `(list[PylintMessage], None)` as today.
- Invalid entry: `([], "<error string>")`.
- `{"path": "Command line", "line": 1, "column": 0, ...}` is valid.

## Tests (write first)

- Rewrite `test_parse_json_with_non_dict_items` → error, `messages == []`.
- Rewrite `test_parse_json_with_missing_fields` → error mentioning the cause.
- `test_non_dict_first_entry_is_error` — `["x", {...valid...}]` → error, no crash.
- `test_non_int_line_is_error` — `line: "1"` → error.
- `test_command_line_entry_parses` — `path: "Command line"`, `line: 1`,
  `column: 0` → one message.
