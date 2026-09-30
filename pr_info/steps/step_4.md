# Step 4 — Strict bandit parser and CWE line

## LLM prompt

Read `pr_info/steps/summary.md`, then implement `pr_info/steps/step_4.md`.
Write the tests first, then the implementation. Run pylint, pytest
(`-n auto -m "not integration"`) and mypy; all must pass. One commit.

## WHERE

- `src/mcp_tools_py/code_checker_bandit/parsers.py`
- `src/mcp_tools_py/code_checker_bandit/reporting.py`
- `tests/test_code_checker_bandit/test_parsers.py`
- `tests/test_code_checker_bandit/test_reporting.py`

## WHAT

```python
def _invalid_reason(item: object) -> str | None:
    """Why a bandit result entry cannot be used as a finding, or None if valid."""

def parse_bandit_json_output(raw_output: str, project_dir: str
) -> tuple[list[BanditMessage], list[str], str | None]   # signature unchanged
```

`BanditMessage` is unchanged; `cwe_id == 0` means "no CWE id".

## HOW

- Parser, after the `isinstance(data, dict)` check:
  `results = data.get("results")`; if not a list, return
  `"bandit output has no 'results' list (keys: ...)"` as the parse error.
- Replace the "skip non-dict" branch with `_invalid_reason`.
- CWE: keep the `isinstance(issue_cwe, dict)` guard;
  `cwe_id = (issue_cwe.get("id") or 0) if isinstance(issue_cwe, dict) else 0`
  (handles missing, `null` and non-dict `issue_cwe`).
- Reporting: emit `f"CWE-{first.cwe_id}: {first.cwe_link}"` only when
  `first.cwe_id` is truthy.

## ALGORITHM

```
_invalid_reason(item):
    if not dict: return "results that are not objects"
    if test_id or filename is missing or None: return "results without test_id or filename"
    if line_number is not an int (bool excluded): return "results without line numbers"
    return None

parse: for item in results: reason -> return [], [], f"bandit returned {reason} (keys: {keys}); an argument in extra_args probably changed the output shape."
```

## DATA

- Valid input: `(messages, file_errors, None)` as today.
- Missing/non-list `results` or invalid entry: `([], [], "<error string>")`.

## Tests (write first)

Parser:
- `test_missing_results_is_error` — `{"errors": []}` → error.
- `test_non_list_results_is_error` — `{"results": {}}` → error.
- `test_non_dict_result_is_error`, `test_missing_line_number_is_error`,
  `test_missing_test_id_is_error`.
- Update `test_parse_missing_cwe_fields`: still `cwe_id == 0`, `cwe_link == ""`;
  add a case with `issue_cwe: {"id": None}`.

Reporting:
- `test_format_omits_cwe_line_without_id` — `cwe_id=0` → `"CWE-"` not in report.
- Existing `test_format_includes_cwe_reference` keeps passing.
